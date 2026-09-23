import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useCamera, type Region } from "@/hooks/useCamera";
import { beep } from "@/lib/beep";
import { toast } from "@/lib/toast";

import { CardCapture } from "./CardCapture";
import { replaceSide, type CardSide } from "./cardSide";
import { CardViewfinder } from "./CardViewfinder";
import { cardBox } from "./frameAnalysis";
import { useAutoCapture } from "./useAutoCapture";

type Target = "front" | "back";

const FLASH_MS = 700;

/** Both sides of one card, filled by one camera session: the front is taken when it is held
 * still in the guide, the caption asks for the back, the back is taken, the camera closes. Each
 * side keeps its file picker, and either can be retaken alone (UC-125). */
export function CardPairCapture({
  frontLabel,
  backLabel,
  front,
  back,
  onFront,
  onBack,
  disabled = false,
}: {
  frontLabel: string;
  backLabel: string;
  front: CardSide | null;
  back: CardSide | null;
  onFront: (side: CardSide | null) => void;
  onBack: (side: CardSide | null) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const camera = useCamera();
  const [target, setTarget] = useState<Target | null>(null);
  // The side just taken, while its green flash lasts — named in the caption even though the
  // target has already moved on to the other side.
  const [taken, setTaken] = useState<Target | null>(null);
  const flashTimer = useRef(0);
  useEffect(() => () => window.clearTimeout(flashTimer.current), []);

  // The loop and the shutter both land here; refs so a capture fired from the loop's timer sees
  // the sides as they are now, not as they were when the loop started.
  const sides = useRef({ front, back, target });
  sides.current = { front, back, target };

  const take = async (region: Region) => {
    const which = sides.current.target;
    if (!which) return;
    const file = await camera.capture(`${which}.jpg`, region);
    if (!file) return;
    if (which === "front") onFront(replaceSide(sides.current.front, file));
    else onBack(replaceSide(sides.current.back, file));
    beep();
    setTaken(which);
    window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setTaken(null), FLASH_MS);
    // Front taken and the back still empty: stay open and ask for it. Anything else is done.
    if (which === "front" && !sides.current.back) setTarget("back");
    else finish();
  };

  const auto = useAutoCapture({ videoRef: camera.videoRef, enabled: camera.active, onCapture: take });

  const finish = () => {
    camera.stop();
    setTarget(null);
  };

  const openFor = async (which: Target) => {
    setTarget(which);
    if (camera.active) return;
    if (!(await camera.open())) {
      setTarget(null);
      toast.error(t("cardScan.cameraDenied"));
    }
  };

  const shoot = () => {
    const video = camera.videoRef.current;
    if (!video?.videoWidth) return;
    auto.lock();
    void take(cardBox(video.videoWidth, video.videoHeight));
  };

  const labelOf = (which: Target | null) => (which === "back" ? backLabel : frontLabel);

  return (
    <div className="space-y-4">
      {camera.active && target ? (
        <CardViewfinder
          videoRef={camera.videoRef}
          phase={auto.phase}
          flash={taken != null}
          target={labelOf(taken ?? target)}
          onShoot={shoot}
          onCancel={finish}
        />
      ) : null}
      <div className="grid gap-6 md:grid-cols-2">
        <CardCapture
          label={frontLabel}
          hint={t("cardScan.frontHint")}
          side={front}
          onChange={onFront}
          onUseCamera={() => openFor("front")}
          disabled={disabled}
        />
        <CardCapture
          label={backLabel}
          hint={t("cardScan.backHint")}
          side={back}
          onChange={onBack}
          onUseCamera={() => openFor("back")}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
