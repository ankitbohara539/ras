import { MapPinned } from "lucide-react";
import Link from "next/link";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="brand" aria-label="CivicGrid home">
      <span className="brand-mark"><MapPinned size={20} /></span>
      {!compact && <span>CivicGrid</span>}
    </Link>
  );
}
