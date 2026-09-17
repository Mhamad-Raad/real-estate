let context: AudioContext | null = null;

/** A short confirmation tone — the "card taken" sound. Silent wherever WebAudio is missing. */
export function beep(frequency = 880, ms = 120) {
  try {
    context ??= new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = frequency;
    oscillator.connect(gain);
    gain.connect(context.destination);
    gain.gain.setValueAtTime(0.08, context.currentTime);
    oscillator.start();
    oscillator.stop(context.currentTime + ms / 1000);
  } catch {
    // No audio device, or autoplay blocked: the green flash carries the message on its own.
  }
}
