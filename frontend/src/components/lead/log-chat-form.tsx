"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { useLogMessages } from "@/hooks/use-lead-mutations";
import { ApiError } from "@/lib/api";
import { businessLocalToIso, businessNowLocal } from "@/lib/format";

const MAX_MESSAGES = 20;

function schema(timeZone: string) {
  return z.object({
    messages: z
      .array(
        z.object({
          sender: z.enum(["buyer", "rep"]),
          body: z
            .string()
            .trim()
            .min(1, "Write the message text.")
            .max(2000, "Keep it under 2000 characters."),
          when: z
            .string()
            .refine(
              (value) => !value || value <= businessNowLocal(timeZone),
              "This time is in the future.",
            ),
        }),
      )
      .min(1)
      .max(MAX_MESSAGES),
  });
}

type FormValues = z.infer<ReturnType<typeof schema>>;
const EMPTY = { sender: "buyer" as const, body: "", when: "" };

function newRequestId(): string {
  return globalThis.crypto.randomUUID();
}

export function LogChatForm({
  leadId,
  timeZone,
  onDone,
}: {
  leadId: string;
  timeZone: string;
  onDone?: () => void;
}) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema(timeZone)),
    defaultValues: { messages: [EMPTY] },
    mode: "onSubmit",
  });
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "messages" });
  // One id per submission attempt, reused on retry, so a double click or a network retry can't
  // log the same chat twice. A new id is minted only after a successful save.
  const [requestId, setRequestId] = useState(newRequestId);
  const log = useLogMessages(leadId);

  const onSubmit = form.handleSubmit((values) => {
    log.mutate(
      {
        client_request_id: requestId,
        messages: values.messages.map((m) => ({
          sender_type: m.sender,
          body: m.body.trim(),
          ...(m.when ? { sent_at: businessLocalToIso(m.when, timeZone) } : {}),
        })),
      },
      {
        onSuccess: () => {
          setRequestId(newRequestId());
          form.reset({ messages: [EMPTY] });
          toast.success("Chat logged. The agent is re-reading the conversation…");
          onDone?.();
        },
        onError: (error) =>
          toast.error(
            error instanceof ApiError && error.status !== 0
              ? error.message
              : "Couldn't save the chat. Your text is kept; try again.",
          ),
      },
    );
  });

  const max = businessNowLocal(timeZone);

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {fields.map((field, index) => {
        const errors = form.formState.errors.messages?.[index];
        const bodyId = `log-${leadId}-${field.id}`;
        return (
          <fieldset key={field.id} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center justify-between gap-2">
              <legend className="sr-only">Message {index + 1}</legend>
              <Controller
                control={form.control}
                name={`messages.${index}.sender`}
                render={({ field: sender }) => (
                  <RadioGroup
                    value={sender.value}
                    onValueChange={sender.onChange}
                    className="flex gap-4"
                    aria-label={`Who wrote message ${index + 1}`}
                  >
                    {(["buyer", "rep"] as const).map((value) => (
                      <div key={value} className="flex items-center gap-1.5">
                        <RadioGroupItem value={value} id={`${bodyId}-${value}`} />
                        <Label htmlFor={`${bodyId}-${value}`} className="text-sm font-normal">
                          {value === "buyer" ? "Buyer" : "Rep"}
                        </Label>
                      </div>
                    ))}
                  </RadioGroup>
                )}
              />
              {index > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove message ${index + 1}`}
                  onClick={() => remove(index)}
                >
                  <X aria-hidden />
                </Button>
              )}
            </div>
            <Textarea
              id={bodyId}
              aria-label={`Message ${index + 1}`}
              aria-invalid={Boolean(errors?.body)}
              aria-describedby={errors?.body ? `${bodyId}-error` : undefined}
              rows={2}
              placeholder="Paste or type what was said"
              className="text-base"
              {...form.register(`messages.${index}.body`)}
            />
            {errors?.body && (
              <p id={`${bodyId}-error`} className="text-xs text-destructive">
                {errors.body.message}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Label
                htmlFor={`${bodyId}-when`}
                className="text-xs font-normal text-muted-foreground"
              >
                When (optional, defaults to now)
              </Label>
              <Input
                id={`${bodyId}-when`}
                type="datetime-local"
                max={max}
                aria-invalid={Boolean(errors?.when)}
                className="h-9 w-auto"
                {...form.register(`messages.${index}.when`)}
              />
              {errors?.when && <p className="text-xs text-destructive">{errors.when.message}</p>}
            </div>
          </fieldset>
        );
      })}
      <div className="flex flex-wrap items-center gap-2">
        {fields.length < MAX_MESSAGES && (
          <Button
            type="button"
            variant="ghost"
            className="border border-dashed border-input-border"
            onClick={() => append({ ...EMPTY, sender: fields.length % 2 ? "buyer" : "rep" })}
          >
            <Plus aria-hidden />
            Add another message
          </Button>
        )}
        <Button
          type="submit"
          variant="secondary"
          size="lg"
          disabled={log.isPending}
          className="ml-auto"
        >
          Log chat
        </Button>
      </div>
    </form>
  );
}
