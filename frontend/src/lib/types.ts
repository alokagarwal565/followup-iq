import type { components } from "./api-types";

type Schemas = components["schemas"];

export type LeadRow = Schemas["LeadRow"];
export type Lead = Schemas["LeadOut"];
export type Message = Schemas["MessageOut"];
export type Draft = Schemas["DraftOut"];
export type LeadDetail = Schemas["LeadDetailOut"];
export type LeadList = Schemas["LeadListOut"];
export type Summary = Schemas["SummaryOut"];
export type Meta = Schemas["MetaOut"];
export type Ready = Schemas["ReadyOut"];
export type LeadCreate = Schemas["LeadCreateIn"];
export type LeadUpdate = Schemas["LeadUpdateIn"];
export type MessagesCreate = Schemas["MessagesIn"];
export type DraftSave = Schemas["DraftSaveIn"];
export type DraftSend = Schemas["DraftSendIn"];

export type Classification = NonNullable<LeadRow["classification"]>;
export type DueState = LeadRow["due_state"];

export interface LeadFilters {
  rep?: string;
  q?: string;
  classification?: Classification;
  due_state?: DueState;
}
