import Image from "next/image";

import solanaSrc from "@/assets/chains/SOLANA.webp";

function SOLANA() {
  return <Image src={solanaSrc} width="24" height="24" alt={"solana-logo"} />;
}

export default SOLANA;
