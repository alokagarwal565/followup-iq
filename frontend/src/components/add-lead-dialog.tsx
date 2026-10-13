"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateLead } from "@/hooks/use-lead-mutations";
import { ApiError } from "@/lib/api";
import type { Meta } from "@/lib/types";

const phonePattern = /^\+?[0-9 ()-]{7,20}$/;

function schema(today: string) {
  return z.object({
    name: z
      .string()
      .trim()
      .min(1, "Enter the contact's name.")
      .max(120, "Keep it under 120 characters."),
    company: z
      .string()
      .trim()
      .min(1, "Enter the company name.")
      .max(160, "Keep it under 160 characters."),
    phone: z
      .string()
      .trim()
      .refine(
        (value) => {
          const digits = value.replace(/\D/g, "").length;
          return phonePattern.test(value) && digits >= 7 && digits <= 15;
        },
        { message: "Enter a phone number with 7 to 15 digits." },
      ),
    source: z.string().min(1),
    assigned_rep: z.string().min(1),
    last_contact_date: z
      .string()
      .refine((value) => !value || value <= today, "The last contact can't be in the future."),
    first_message: z.string().trim().max(2000, "Keep it under 2000 characters."),
  });
}

type Values = z.infer<ReturnType<typeof schema>>;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  meta: Meta;
  defaultRep: string | null;
  onCreated: (id: string) => void;
  onOpenExisting: (id: string) => void;
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="text-xs text-destructive">
      {message}
    </p>
  );
}

export function AddLeadDialog({
  open,
  onOpenChange,
  meta,
  defaultRep,
  onCreated,
  onOpenExisting,
}: Props) {
  const defaults: Values = {
    name: "",
    company: "",
    phone: "",
    source: meta.sources.includes("WhatsApp") ? "WhatsApp" : meta.sources[0],
    assigned_rep: defaultRep ?? meta.reps[0],
    last_contact_date: "",
    first_message: "",
  };
  const form = useForm<Values>({
    resolver: zodResolver(schema(meta.today)),
    defaultValues: defaults,
    mode: "onBlur",
  });
  const [existingId, setExistingId] = useState<string | null>(null);
  // One id per new lead, reused on retry, so a double click cannot create the same lead twice.
  const [requestId, setRequestId] = useState(() => globalThis.crypto.randomUUID());
  const create = useCreateLead();
  const errors = form.formState.errors;

  const close = (next: boolean) => {
    if (!next) {
      form.reset(defaults);
      setExistingId(null);
      setRequestId(globalThis.crypto.randomUUID());
    }
    onOpenChange(next);
  };

  const onSubmit = form.handleSubmit((values) => {
    setExistingId(null);
    create.mutate(
      {
        name: values.name,
        company: values.company,
        phone: values.phone,
        source: values.source,
        assigned_rep: values.assigned_rep,
        last_contact_date: values.last_contact_date || null,
        messages: values.first_message
          ? [{ sender_type: "buyer", body: values.first_message }]
          : [],
        client_request_id: requestId,
      },
      {
        onSuccess: (created) => {
          toast.success(`${created.lead.name} added. Analysing…`);
          onCreated(created.lead.id);
          close(false);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "duplicate_phone") {
            form.setError("phone", { message: "A lead with this phone number already exists." });
            const existing = error.details?.existing_lead_id;
            setExistingId(typeof existing === "string" ? existing : null);
            return;
          }
          toast.error(
            error instanceof ApiError ? error.message : "Couldn't add the lead. Please try again.",
          );
        },
      },
    );
  });

  const text = (
    name: "name" | "company" | "phone",
    label: string,
    type = "text",
    autoComplete?: string,
  ) => (
    <div className="space-y-1.5">
      <Label htmlFor={`add-${name}`}>{label}</Label>
      <Input
        id={`add-${name}`}
        type={type}
        autoComplete={autoComplete}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={errors[name] ? `add-${name}-error` : undefined}
        {...form.register(name)}
      />
      <FieldError id={`add-${name}-error`} message={errors[name]?.message} />
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add lead</DialogTitle>
          <DialogDescription>
            The agent tags the new lead, sets its follow-up date and drafts the first message.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {text("name", "Name", "text", "name")}
          {text("company", "Company", "text", "organization")}
          {text("phone", "Phone", "tel", "tel")}
          {existingId && (
            <Button type="button" variant="outline" onClick={() => onOpenExisting(existingId)}>
              Open existing lead
            </Button>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                ["source", "Source", meta.sources],
                ["assigned_rep", "Assigned rep", meta.reps],
              ] as const
            ).map(([name, label, options]) => (
              <div key={name} className="space-y-1.5">
                <Label htmlFor={`add-${name}`}>{label}</Label>
                <Controller
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={`add-${name}`} className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {options.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            ))}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="add-last_contact_date">Last contact (optional)</Label>
            <Input
              id="add-last_contact_date"
              type="date"
              max={meta.today}
              aria-invalid={Boolean(errors.last_contact_date)}
              aria-describedby={
                errors.last_contact_date ? "add-last_contact_date-error" : undefined
              }
              {...form.register("last_contact_date")}
            />
            <FieldError
              id="add-last_contact_date-error"
              message={errors.last_contact_date?.message}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="add-first_message">Buyer&apos;s first message (optional)</Label>
            <Textarea
              id="add-first_message"
              rows={3}
              placeholder="Paste the enquiry, if there is one"
              aria-invalid={Boolean(errors.first_message)}
              {...form.register("first_message")}
            />
            <FieldError id="add-first_message-error" message={errors.first_message?.message} />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="submit" size="lg" disabled={create.isPending}>
              Add lead
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
