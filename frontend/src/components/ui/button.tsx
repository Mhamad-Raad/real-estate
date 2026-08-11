import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

// Not exported: nothing outside this file has ever used it, and exporting a non-component
// from a component module is what breaks Fast Refresh for the whole file (It.8).
// `disabled:cursor-not-allowed` in place of the usual `disabled:pointer-events-none`: with events
// off the cursor cannot apply at all, so a disabled button silently showed the plain arrow while
// every other disabled control in the app (input, select, checkbox, textarea) says "not allowed".
//
// The trade that buys is hover: without `pointer-events-none`, a disabled button would light up
// under the mouse. Hence **`not-disabled:hover:`** on every variant. Not `enabled:hover:` — that
// resolves to `:enabled`, which only matches form controls, and `asChild` renders some of these as
// `<Link>` anchors (ClientsPage, NotFoundPage) whose hover would then be dead. `:not(:disabled)` is
// true for an anchor and false for a disabled button, which is exactly the distinction wanted.
// Clicks need no guard: a native `disabled` button does not fire them.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground not-disabled:hover:bg-primary/90 shadow-sm",
        destructive:
          "bg-destructive text-destructive-foreground not-disabled:hover:bg-destructive/90 shadow-sm",
        outline:
          "border border-input bg-background not-disabled:hover:bg-accent not-disabled:hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground not-disabled:hover:bg-secondary/80",
        ghost: "not-disabled:hover:bg-accent not-disabled:hover:text-accent-foreground",
        link: "text-primary underline-offset-4 not-disabled:hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-6",
        icon: "size-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
