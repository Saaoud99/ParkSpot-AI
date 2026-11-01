/** Deterministic grounded assistant core (no LLM).
 *
 * Answers exclusively from the facility rows it is given — it cannot invent
 * facilities, prices or availability, and it never claims to be an AI model.
 * Used by the /api/chat server route as the always-available fallback when
 * the FastAPI backend (Muse Spark / grounded mode) is not connected.
 */

export type AssistantFacility = {
  id: string;
  name: string;
  city: string;
  address: string;
  price_per_hour_cents: number;
  available: number;
  capacity: number;
  features: string[];
  rating: number | string;
};

const CITIES: Record<string, string[]> = {
  Casablanca: ["casablanca", "casa", "الدار البيضاء", "كازا"],
  Rabat: ["rabat", "الرباط"],
  Marrakech: ["marrakech", "marrakesh", "مراكش"],
  Tangier: ["tangier", "tanger", "طنجة"],
};
const FEATURES: Record<string, string[]> = {
  ev: ["ev charging", "electric", "charging", "charge my", "شحن", "كهرباء"],
  covered: ["covered", "indoor", "garage", "مغطى", "مرآب"],
  cctv: ["cctv", "camera", "secure", "security", "مراقبة", "أمان"],
  valet: ["valet"],
};

function findKey(text: string, table: Record<string, string[]>): string | null {
  for (const [key, words] of Object.entries(table))
    if (words.some((w) => text.includes(w))) return key;
  return null;
}

function findFeature(text: string): string | null {
  // Bare "ev" needs a word boundary — as a substring it also hits "every".
  if (/\bev\b/.test(text)) return "ev";
  return findKey(text, FEATURES);
}

export function groundedReply(
  facilities: AssistantFacility[],
  message: string,
  lang = "en",
): string {
  const text = message.toLowerCase();
  const ar = lang === "ar" || /[؀-ۿ]/.test(message);

  if (
    (text.includes("refund") || text.includes("استرداد") || text.includes("cancel")) &&
    !findKey(text, CITIES)
  ) {
    return ar
      ? "سياسة الاسترداد: استرداد كامل قبل ساعتين أو أكثر من بدء الحجز، 50٪ قبل البدء، ولا استرداد بعد البدء. يمكنك الإلغاء من صفحة حجوزاتي."
      : "Refund policy: full refund 2h or more before your booking starts, 50% until it starts, none after. Cancel from My Bookings.";
  }
  if (["near me", "nearby", "قريب مني", "près de moi"].some((w) => text.includes(w))) {
    return ar
      ? "لا أستطيع معرفة موقعك من المحادثة. اضغط «مواقف قربي» في الرئيسية، أو أخبرني بالمدينة."
      : "I can't get your location from chat. Tap “Parking Near Me” on Home, or tell me a city (Casablanca, Rabat, Marrakech, Tangier).";
  }

  let rows = facilities.filter((f) => f.available > 0);
  const city = findKey(text, CITIES);
  if (city) rows = rows.filter((f) => f.city === city);
  const feature = findFeature(text);
  if (feature) rows = rows.filter((f) => (f.features ?? []).includes(feature));
  const priceMatch =
    text.match(/(\d+(?:[.,]\d+)?)\s*(?:mad|dh|درهم)/) ||
    text.match(/(?:under|below|less than|أقل من)\s*(\d+(?:[.,]\d+)?)/);
  if (priceMatch) {
    const max = Number(priceMatch[1].replace(",", ".")) * 100;
    rows = rows.filter((f) => f.price_per_hour_cents <= max);
  }
  const cheapest = ["cheapest", "cheap", "أرخص", "رخيص", "moins cher"].some((w) =>
    text.includes(w),
  );
  rows = [...rows]
    .sort((a, b) =>
      cheapest
        ? a.price_per_hour_cents - b.price_per_hour_cents
        : Number(b.rating) - Number(a.rating),
    )
    .slice(0, 5);

  if (!rows.length) {
    return ar
      ? "لم أجد مواقف مطابقة في المخزون الحقيقي. جرّب مدينة أخرى أو وسّع البحث."
      : "I found no matching parking in the real inventory. Try another city or widen the search.";
  }
  const hoursMatch = text.match(/(\d{1,2})\s*(?:h\b|hours?|ساعات|ساعة)/);
  const lines = rows.map(
    (f) =>
      `• ${f.name} (${f.city}) — ${(f.price_per_hour_cents / 100).toFixed(2)} ${ar ? "درهم/ساعة" : "MAD/h"}, ${f.available}/${f.capacity} ${ar ? "متاح" : "free"}`,
  );
  let out = `${ar ? "إليك مواقف حقيقية متاحة الآن:" : "Here are real facilities available now:"}\n${lines.join("\n")}`;
  if (hoursMatch) {
    const hours = Math.max(1, Math.min(24, Number(hoursMatch[1])));
    out += `\n💰 ${hours}${ar ? " ساعة" : "h"} = ${((rows[0].price_per_hour_cents * hours) / 100).toFixed(2)} ${ar ? "درهم" : "MAD"} (${rows[0].name})`;
  }
  return (
    out +
    (ar
      ? "\nافتح أي موقف من الرئيسية أو الخريطة للحجز."
      : "\nOpen any facility from Home or the Map to book.")
  );
}
