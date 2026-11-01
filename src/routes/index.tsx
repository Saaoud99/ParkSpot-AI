import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Phone } from "@/components/AppShell";
import { useI18n } from "@/lib/i18n";
import logo from "@/assets/logo.png";
import garage from "@/assets/garage.jpg";
import rooftop from "@/assets/rooftop.jpg";
import openlot from "@/assets/openlot.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ParkSpot AI — Smarter Parking. Easier Journeys." },
      {
        name: "description",
        content:
          "Discover parking across Morocco, pay with ParkSpot Wallet and get help from an AI assistant.",
      },
      { property: "og:title", content: "ParkSpot AI" },
      { property: "og:description", content: "Smarter Parking. Easier Journeys." },
    ],
  }),
  component: Splash,
});

function Splash() {
  const { t, lang, setLang } = useI18n();
  const nav = useNavigate();
  const [stage, setStage] = useState<"splash" | "onboard">("splash");
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => {
      if (localStorage.getItem("ps-onboarded")) nav({ to: "/home" });
      else setStage("onboard");
    }, 1400);
    return () => clearTimeout(id);
  }, [nav]);

  const finish = (to: "/home" | "/auth") => {
    localStorage.setItem("ps-onboarded", "1");
    nav({ to });
  };

  if (stage === "splash") {
    return (
      <Phone>
        <div className="flex flex-1 flex-col items-center justify-center bg-brand text-primary-foreground">
          <div className="rounded-[2rem] bg-card p-5 shadow-lift animate-in zoom-in-75 duration-700">
            <img
              src={logo}
              alt="ParkSpot AI"
              width={88}
              height={88}
              className="h-20 w-20 object-contain"
            />
          </div>
          <h1 className="mt-6 font-display text-3xl font-semibold animate-in fade-in slide-in-from-bottom-2 duration-700">
            ParkSpot AI
          </h1>
          <p className="mt-2 text-sm opacity-80">{t("tagline")}</p>
        </div>
      </Phone>
    );
  }

  const slides = [
    { img: garage, title: t("ob1t"), body: t("ob1b") },
    { img: rooftop, title: t("ob2t"), body: t("ob2b") },
    { img: openlot, title: t("ob3t"), body: t("ob3b") },
  ];
  const s = slides[step]!;
  return (
    <Phone>
      <div className="relative h-[58vh] min-h-[380px] md:h-[480px]">
        <img
          key={s.img}
          src={s.img}
          alt=""
          className="h-full w-full object-cover animate-in fade-in duration-500"
        />
        <div className="absolute inset-0 bg-fade" />
        <div className="absolute inset-x-0 top-0 flex justify-between p-5">
          <button
            onClick={() => setLang(lang === "en" ? "ar" : "en")}
            className="rounded-full bg-card/90 px-3 py-1 text-xs font-semibold"
          >
            {lang === "en" ? "العربية" : "English"}
          </button>
          <button
            onClick={() => finish("/home")}
            className="rounded-full bg-card/90 px-3 py-1 text-xs font-semibold"
          >
            {t("skip")}
          </button>
        </div>
      </div>
      <div className="app-scroll -mt-8 flex min-h-0 flex-1 flex-col rounded-t-[2rem] bg-background px-6 pb-8 pt-7">
        <div className="flex gap-1.5">
          {slides.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${i === step ? "w-8 bg-primary" : "w-3 bg-border"}`}
            />
          ))}
        </div>
        <h2 className="mt-5 font-display text-3xl font-semibold leading-tight">{s.title}</h2>
        <p className="mt-3 text-muted-foreground">{s.body}</p>
        <div className="mt-auto space-y-3 pt-8">
          {step < 2 ? (
            <button
              onClick={() => setStep(step + 1)}
              className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift"
            >
              {t("next")}
            </button>
          ) : (
            <>
              <button
                onClick={() => finish("/auth")}
                className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift"
              >
                {t("getStarted")}
              </button>
              <button
                onClick={() => finish("/home")}
                className="h-12 w-full rounded-full border font-semibold"
              >
                {t("explore")}
              </button>
            </>
          )}
        </div>
      </div>
    </Phone>
  );
}
