import type { Client, ClientInput } from "./types";

export type ClientDraft = ClientInput;

/** Map a saved client to the editable shape, dropping server-owned fields like id/version. */
export function toInput(client: Client): ClientInput {
  return {
    full_name: client.full_name,
    pid: client.pid,
    mother_full_name: client.mother_full_name,
    marital_status: client.marital_status,
    spouse_name: client.spouse_name,
    spouse_date_of_birth: client.spouse_date_of_birth,
    spouse_mother_full_name: client.spouse_mother_full_name,
    spouse_pid: client.spouse_pid,
    date_of_birth: client.date_of_birth,
    place_of_birth: client.place_of_birth,
    address: client.address,
    phone: client.phone,
    category: client.category,
  };
}

export const EMPTY_CLIENT: ClientInput = {
  full_name: "",
  pid: "",
  mother_full_name: "",
  marital_status: "single",
  spouse_name: "",
  spouse_pid: "",
  spouse_date_of_birth: null,
  spouse_mother_full_name: "",
  date_of_birth: null,
  place_of_birth: "",
  address: "",
  phone: "",
  category: null,
};

/**
 * Blank the spouse details when a client is not married.
 *
 * A divorce must not leave a former spouse printed on the next letter, and a stale `spouse_pid`
 * would keep flagging the household as already allocated and block an application they may
 * legitimately make (§5.7, §6.6).
 */
export function withMaritalRules(form: ClientInput): ClientInput {
  const married = form.marital_status === "married";
  return {
    ...form,
    date_of_birth: form.date_of_birth || null,
    spouse_name: married ? form.spouse_name : "",
    spouse_date_of_birth: married ? form.spouse_date_of_birth || null : null,
    spouse_mother_full_name: married ? form.spouse_mother_full_name : "",
    spouse_pid: married ? form.spouse_pid : "",
  };
}
