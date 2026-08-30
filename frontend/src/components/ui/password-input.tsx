import { Eye, EyeOff } from "lucide-react";
import * as React from "react";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * A password field you can check by **holding** the eye, not by toggling it (UC-077).
 *
 * Hold-to-reveal rather than a sticky switch on purpose: these are shared office desks, so a
 * revealed password must never be able to outlive the moment someone is reading it — releasing,
 * moving the pointer away or tabbing off all hide it again.
 */
export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }
>(({ className, disabled, ...props }, ref) => {
  const { t } = useTranslation();
  const [revealed, setRevealed] = React.useState(false);
  const hide = () => setRevealed(false);

  return (
    <div className="relative">
      {/* Logical padding, so the text stops short of the button in RTL as well as LTR. */}
      <Input
        ref={ref}
        type={revealed ? "text" : "password"}
        className={cn("pe-10", className)}
        disabled={disabled}
        {...props}
      />
      {!disabled && (
        <button
          type="button"
          // Without this the eye would submit the form it sits in.
          aria-label={t("auth.holdToShow")}
          aria-pressed={revealed}
          className="absolute inset-y-0 end-0 flex items-center px-3 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:text-foreground"
          onPointerDown={() => setRevealed(true)}
          onPointerUp={hide}
          onPointerLeave={hide}
          onPointerCancel={hide}
          // Keyboard equivalent of holding: revealed while the key is down, hidden on release.
          onKeyDown={(e) => (e.key === " " || e.key === "Enter") && setRevealed(true)}
          onKeyUp={hide}
          onBlur={hide}
        >
          {revealed ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      )}
    </div>
  );
});
PasswordInput.displayName = "PasswordInput";
