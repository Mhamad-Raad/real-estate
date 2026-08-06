/** The imperative toast API, re-exported from one place.
 *
 * It lived in `components/ui/toaster.tsx` next to the `<Toaster />` component, which made that
 * file export both a component and a value — the thing that turns Fast Refresh off for the module
 * (the `only-export-components` warning carried since It.0). The component stays there; the
 * function lives here, so features import behaviour from a plain module.
 */
export { toast } from "sonner";
