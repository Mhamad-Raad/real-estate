import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { FormSection } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { useFieldErrors } from "@/hooks/useFieldErrors";
import { FieldError } from "@/components/ui/field-error";

import { useCreateUserMutation, useUpdateUserMutation } from "./usersApi";
import type { AdminUser, Role } from "./types";

const EMPTY = { username: "", first_name: "", last_name: "", email: "", role: "lawyer" as Role };

// Create/edit a user account. In edit mode the password field is optional (blank = keep current).
export function UserFormDialog({
  open,
  user,
  onClose,
}: {
  open: boolean;
  user: AdminUser | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [create, { isLoading: creating }] = useCreateUserMutation();
  const [update, { isLoading: updating }] = useUpdateUserMutation();
  const [form, setForm] = useState(EMPTY);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const { errors, setFromError, clear, clearAll } = useFieldErrors();

  useEffect(() => {
    if (open) {
      setForm(
        user
          ? {
              username: user.username,
              first_name: user.first_name,
              last_name: user.last_name,
              email: user.email,
              role: user.role,
            }
          : EMPTY,
      );
      setPassword("");
      setConfirm("");
      setMismatch(false);
      clearAll(); // reopening on a different user must not inherit the last one's errors
    }
  }, [open, user, clearAll]);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => {
    clear(key);
    setForm((f) => ({ ...f, [key]: e.target.value }));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Checked here rather than server-side: the server only ever receives one password, so a typo
    // would create an account nobody can sign into — and there is no reset on an offline machine.
    if (password !== confirm) {
      setMismatch(true);
      toast.error(t("users.passwordMismatch"));
      return;
    }
    try {
      if (user) {
        await update({
          id: user.id,
          version: user.version,
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role: form.role,
          ...(password ? { password } : {}),
        }).unwrap();
      } else {
        await create({
          username: form.username,
          password,
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          role: form.role,
        }).unwrap();
      }
      toast.success(t("common.saved"));
      onClose();
    } catch (err) {
      setFromError(err);
      toast.error(apiErrorMessage(err, t("common.saveError"), labeller(t), t));
    }
  };

  const busy = creating || updating;
  return (
    <Dialog open={open} onClose={onClose} title={user ? t("users.edit") : t("users.add")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="u-username">{t("users.username")}</Label>
          <Input
            id="u-username"
            value={form.username}
            onChange={set("username")}
            required
            disabled={Boolean(user)}
            autoFocus={!user}
            invalid={Boolean(errors.username)}
            aria-describedby={errors.username ? "u-username-error" : undefined}
          />
          <FieldError id="u-username-error" message={errors.username} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="u-first">{t("users.firstName")}</Label>
            <Input id="u-first" value={form.first_name} onChange={set("first_name")} invalid={Boolean(errors.first_name)} />
            <FieldError message={errors.first_name} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="u-last">{t("users.lastName")}</Label>
            <Input id="u-last" value={form.last_name} onChange={set("last_name")} invalid={Boolean(errors.last_name)} />
            <FieldError message={errors.last_name} />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-email">{t("users.email")}</Label>
          <Input id="u-email" type="email" value={form.email} onChange={set("email")} invalid={Boolean(errors.email)} />
          <FieldError message={errors.email} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-role">{t("users.role")}</Label>
          <Select id="u-role" value={form.role} onChange={set("role")}>
            <option value="lawyer">{t("role.lawyer")}</option>
            <option value="admin">{t("role.admin")}</option>
          </Select>
        </div>

        {/* Its own section rather than a box beside the role (UC-077): setting a password is a
            different act from correcting a name, and it is the one field here that cannot be
            undone by looking at it — these machines have no internet and no password reset. */}
        <FormSection
          title={user ? t("users.newPassword") : t("users.password")}
          description={user ? t("users.passwordSectionHint") : undefined}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="u-password">
                {user ? t("users.newPassword") : t("users.password")}
              </Label>
              <PasswordInput
                id="u-password"
                value={password}
                onChange={(e) => {
                  clear("password");
                  setMismatch(false);
                  setPassword(e.target.value);
                }}
                autoComplete="new-password"
                placeholder={user ? t("users.passwordKeep") : undefined}
                required={!user}
                invalid={Boolean(errors.password)}
                aria-describedby={errors.password ? "u-password-error" : undefined}
              />
              <FieldError id="u-password-error" message={errors.password} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="u-confirm">{t("users.confirmPassword")}</Label>
              <PasswordInput
                id="u-confirm"
                value={confirm}
                onChange={(e) => {
                  setMismatch(false);
                  setConfirm(e.target.value);
                }}
                autoComplete="new-password"
                required={!user}
                invalid={mismatch}
                aria-describedby={mismatch ? "u-confirm-error" : undefined}
              />
              <FieldError id="u-confirm-error" message={mismatch ? t("users.passwordMismatch") : undefined} />
            </div>
          </div>
        </FormSection>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={busy}>
            {busy && <Spinner />}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
