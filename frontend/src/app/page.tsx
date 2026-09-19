"use client";

import { ArrowUpRight, BellRing, Building2, Map, MapPinned, ShieldCheck, WifiOff } from "lucide-react";
import Link from "next/link";
import { Brand } from "@/components/Brand";
import { PublicLanguageToggle, usePublicLanguage } from "@/features/i18n/public-language";

const capabilities = [
  { icon: Map, en: ["See every ward clearly", "Map verified issues, civic services, and active alerts across Kathmandu's 32 wards."], ne: ["हरेक वडा स्पष्ट रूपमा हेर्नुहोस्", "काठमाडौंका ३२ वडाका प्रमाणित समस्या, नागरिक सेवा र सक्रिय सूचनाहरू नक्सामा हेर्नुहोस्।"] },
  { icon: BellRing, en: ["Coordinate in real time", "Keep residents, ward offices, municipal teams, and responders aligned."], ne: ["वास्तविक समयमा समन्वय", "नागरिक, वडा कार्यालय, महानगर टोली र उद्धारकर्तालाई एउटै सूचनामा जोड्नुहोस्।"] },
  { icon: WifiOff, en: ["Built for local conditions", "Save ordinary reports on weak connections and sync safely when service returns."], ne: ["स्थानीय अवस्थाका लागि तयार", "कमजोर इन्टरनेटमा प्रतिवेदन सुरक्षित राख्नुहोस् र सेवा फर्केपछि पठाउनुहोस्।"] },
];

export default function Home() {
  const { language, text } = usePublicLanguage();
  return (
    <main className="landing" data-language={language}>
      <nav><Brand /><div className="nav-actions"><PublicLanguageToggle compact /><Link href="/login" className="button ghost">{text("Sign in", "साइन इन")}</Link><Link href="/register" className="button primary">{text("Join CivicGrid", "CivicGrid मा जोडिनुहोस्")} <ArrowUpRight size={17} /></Link></div></nav>
      <section className="hero">
        <div>
          <span className="eyebrow"><i /> {text("Kathmandu Metropolitan City", "काठमाडौं महानगरपालिका")}</span>
          <h1>{text("Your ward.", "तपाईंको वडा।")}<br /><em>{text("In clearer focus.", "अब अझ स्पष्ट।")}</em></h1>
          <p>{text("Turn neighborhood reports into visible municipal action—connecting residents, all 32 ward offices, city teams, and emergency responders in one accessible command center.", "टोलका समस्यालाई महानगरको देखिने कार्यमा बदल्नुहोस्—नागरिक, ३२ वटै वडा कार्यालय, महानगर टोली र आपतकालीन उद्धारकर्तालाई एउटै पहुँचयोग्य प्रणालीमा जोड्दै।")}</p>
          <div className="hero-actions"><Link href="/register" className="button primary large">{text("Report a ward issue", "वडाको समस्या रिपोर्ट गर्नुहोस्")} <ArrowUpRight size={19} /></Link><span><ShieldCheck size={18} /> {text("Citizen-first privacy", "नागरिकको गोपनीयता पहिलो")}</span></div>
          <div className="metro-proof"><span><strong>32</strong>{text("Wards", "वडा")}</span><span><strong>1</strong>{text("Shared response network", "साझा प्रतिक्रिया सञ्जाल")}</span><span><MapPinned size={18} />{text("Kathmandu focused", "काठमाडौं केन्द्रित")}</span></div>
        </div>
        <div className="hero-map" aria-hidden="true"><span className="map-pulse one" /><span className="map-pulse two" /><span className="map-pulse three" /><div className="map-label"><Building2 size={18} /><b>32</b><span>{text("connected wards", "जोडिएका वडा")}<br />{text("Kathmandu Metro", "काठमाडौं महानगर")}</span></div></div>
      </section>
      <section className="capabilities">
        {capabilities.map(({ icon: Icon, en, ne }, index) => { const copy = language === "ne" ? ne : en; return <article key={en[0]}><span className="number">0{index + 1}</span><Icon /><h2>{copy[0]}</h2><p>{copy[1]}</p></article>; })}
      </section>
    </main>
  );
}
