import { useEffect, useRef, useState } from 'react';

// C1 block layout within each frame vector F:
//   pose: 33 x 3, left_hand: 21 x 3, right_hand: 21 x 3, face_subset: N x 3,
//   masks: 4. Values are normalized (origin = midpoint of pose 11/12). We draw
//   pose + both hands as points/edges on a canvas and animate across T frames.
const POSE = 33;
const HAND = 21;

interface SkeletonPlayerProps {
  // Decoded float32 landmark sequence of shape [T, F] flattened row-major, or
  // null when the correction carried no landmark blob.
  sequence: Float32Array | null;
  frameVectorSize: number; // F
  frames: number; // T
}

// Minimal pose connections (indices into the 33-point pose block) so the
// animation reads as a body, not a point cloud.
const POSE_EDGES: Array<[number, number]> = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
  [11, 23],
  [12, 24],
  [23, 24],
];

export function SkeletonPlayer({ sequence, frameVectorSize, frames }: SkeletonPlayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [playing, setPlaying] = useState(true);
  const frameRef = useRef(0);

  useEffect(() => {
    if (!sequence) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let raf = 0;
    let last = 0;
    const fps = 15;

    const draw = (ts: number) => {
      if (playing && ts - last > 1000 / fps) {
        last = ts;
        frameRef.current = (frameRef.current + 1) % frames;
      }
      const f = frameRef.current;
      const base = f * frameVectorSize;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const toXY = (idx: number): [number, number] => {
        const o = base + idx * 3;
        // Normalized coords are centered near 0; map to canvas with padding.
        const x = (sequence[o] ?? 0) * canvas.width * 0.4 + canvas.width / 2;
        const y = (sequence[o + 1] ?? 0) * canvas.height * 0.4 + canvas.height / 2;
        return [x, y];
      };

      // Pose edges.
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      for (const [a, b] of POSE_EDGES) {
        const [ax, ay] = toXY(a);
        const [bx, by] = toXY(b);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      }

      // Hands as point clusters.
      const handStart = [POSE * 3, (POSE + HAND) * 3];
      ctx.fillStyle = '#fbbf24';
      for (const start of handStart) {
        for (let i = 0; i < HAND; i++) {
          const o = base + start + i * 3;
          const x = (sequence[o] ?? 0) * canvas.width * 0.4 + canvas.width / 2;
          const y = (sequence[o + 1] ?? 0) * canvas.height * 0.4 + canvas.height / 2;
          ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
        }
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [sequence, frameVectorSize, frames, playing]);

  if (!sequence) {
    return <p className="text-sm text-slate-500">Sin secuencia de landmarks</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      <canvas ref={canvasRef} width={240} height={240} className="rounded border border-slate-300" />
      <button
        type="button"
        className="self-start rounded border border-slate-400 px-3 py-1 text-sm"
        onClick={() => setPlaying((p) => !p)}
      >
        {playing ? 'Pausar' : 'Reproducir'}
      </button>
    </div>
  );
}

// Decode a base64 float16 landmark blob into a Float32Array. Float16 has no
// native typed array, so we convert each 2-byte half to float32.
export function decodeF16Base64(b64: string): Float32Array {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const view = new DataView(bytes.buffer);
  const out = new Float32Array(bytes.byteLength / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = halfToFloat(view.getUint16(i * 2, true));
  }
  return out;
}

function halfToFloat(h: number): number {
  const sign = (h & 0x8000) >> 15;
  const exp = (h & 0x7c00) >> 10;
  const frac = h & 0x03ff;
  if (exp === 0) return (sign ? -1 : 1) * Math.pow(2, -14) * (frac / 1024);
  if (exp === 0x1f) return frac ? NaN : (sign ? -1 : 1) * Infinity;
  return (sign ? -1 : 1) * Math.pow(2, exp - 15) * (1 + frac / 1024);
}
