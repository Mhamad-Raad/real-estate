import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

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
    }
  }, [open, user]);

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      toast.error(apiErrorMessage(err, t("common.saveError")));
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
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="u-first">{t("users.firstName")}</Label>
            <Input id="u-first" value={form.first_name} onChange={set("first_name")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="u-last">{t("users.lastName")}</Label>
            <Input id="u-last" value={form.last_name} onChange={set("last_name")} />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-email">{t("users.email")}</Label>
          <Input id="u-email" type="email" value={form.email} onChange={set("email")} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="u-role">{t("users.role")}</Label>
            <Select id="u-role" value={form.role} onChange={set("role")}>
              <option value="lawyer">{t("role.lawyer")}</option>
              <option value="admin">{t("role.admin")}</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="u-password">
              {user ? t("users.newPassword") : t("users.password")}
            </Label>
            <Input
              id="u-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              placeholder={user ? t("users.passwordKeep") : undefined}
              required={!user}
            />
          </div>
        </div>
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
