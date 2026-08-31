import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/lib/toast";

import { DuplicateWarningDialog } from "./DuplicateWarningDialog";
import { useCheckDuplicateMutation } from "./clientsApi";
import type { DuplicateCheckResult } from "./types";

/**
 * §5.7's pre-save duplicate check, as both screens that create a beneficiary use it.
 *
 * The two of them — the Step-1 intake form and the backlog form (§5.9) — must ask the same
 * question and treat the answer the same way, or a person refused at one door walks in the other.
 * A PID or household match can only be cancelled; a similar mother's name is **advisory** and the
 * lawyer may continue, because it is almost always a sibling.
 *
 * The dialog is the answer to an async question, so `guard` parks on a promise the buttons
 * resolve. That promise is held in a ref: a re-render must not lose the pending decision.
 */
export function useDuplicateGate() {
  const { t } = useTranslation();
  const [checkDuplicate] = useCheckDuplicateMutation();
  const [warning, setWarning] = useState<DuplicateCheckResult | null>(null);
  const decision = useRef<((proceed: boolean) => void) | null>(null);

  /** `true` when it is safe to create — either nothing matched, or the lawyer chose to continue. */
  const guard = async (candidate: {
    pid: string;
    mother_full_name: string;
    spouse_pid?: string;
  }): Promise<boolean> => {
    try {
      const result = await checkDuplicate({ spouse_pid: "", ...candidate }).unwrap();
      const hit =
        result.pid_matches.length ||
        result.household_matches.length ||
        result.mother_name_matches.length;
      if (!hit) return true;
      setWarning(result);
      // **One decision at a time, and it is the dialog's modality that guarantees it.** A second
      // `guard` while one is pending would overwrite this resolver and strand the first promise
      // for ever. It cannot happen today: `Dialog` covers the screen and moves focus into itself,
      // so the form behind can be neither clicked nor Enter-submitted. If this warning ever
      // becomes inline rather than modal, that guarantee goes with it.
      return await new Promise<boolean>((resolve) => {
        decision.current = resolve;
      });
    } catch {
      // A failed check must not silently wave a possible duplicate through.
      toast.error(t("common.loadError"));
      return false;
    }
  };

  const settle = (proceed: boolean) => {
    decision.current?.(proceed);
    decision.current = null;
    setWarning(null);
  };

  /** Render this wherever the screen wants the dialog to live. */
  const dialog = (
    <DuplicateWarningDialog
      open={warning !== null}
      result={warning}
      onProceed={() => settle(true)}
      onClose={() => settle(false)}
    />
  );

  return { guard, dialog };
}
