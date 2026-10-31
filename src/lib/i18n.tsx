import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const en = {
  tagline: "Smarter Parking. Easier Journeys.",
  home: "Home", map: "Map", bookings: "Bookings", wallet: "Wallet", profile: "Profile", assistant: "Assistant",
  hello: "Find your spot", search: "Search city or facility", nearby: "Parking near you",
  perHour: "/ hr", spots: "spots left", full: "Full", book: "Book now", details: "Details",
  signIn: "Sign in", signUp: "Create account", email: "Email", password: "Password", name: "Full name",
  continueGoogle: "Continue with Google", or: "or", haveAccount: "Already have an account?", noAccount: "New to ParkSpot?",
  checkEmail: "Check your email to confirm your account, then sign in.",
  signInToContinue: "Sign in to continue", signInBody: "You need an account for bookings, wallet and profile.",
  available: "Available balance", reserved: "Reserved", deposited: "Total deposited", addMoney: "Add money",
  recent: "Recent transactions", seeAll: "See all", noTx: "No transactions yet. Add money to get started.",
  demoNote: "Demo mode — this is not real money and no card is charged.",
  chooseAmount: "Choose an amount", custom: "Custom amount (MAD)", outcome: "Demo payment outcome",
  succeeded: "Succeeded", failed: "Failed", pending: "Pending", review: "Review", confirmTopup: "Confirm top-up",
  topupDone: "Top-up successful", topupFailed: "Payment failed — no money was added", topupPending: "Payment pending — balance not updated yet",
  history: "Transaction history", topup: "Top-up", booking_charge: "Parking charge", refund: "Refund",
  reviewPay: "Review & pay", start: "Start time", duration: "Duration", hours: "hours", total: "Total due",
  after: "Balance after payment", payWallet: "Pay with wallet", insufficient: "Insufficient balance",
  needMore: "You need {x} more to complete this booking.", confirmed: "Booking confirmed", accessCode: "Access code",
  viewBookings: "View my bookings", cancel: "Cancel booking", cancelled: "Cancelled", active: "Active",
  noBookings: "No bookings yet.", refundPolicy: "Full refund up to 2h before start, 50% until start, none after.",
  vehicle: "Vehicle", plate: "Plate number", model: "Model", phone: "Phone", save: "Save", saved: "Saved",
  logout: "Log out", language: "Language", ops: "Operations", askAI: "Ask about parking, prices, or your bookings…",
  aiHello: "Hi! I'm ParkSpot AI. Ask me where to park, prices, or how the wallet works.",
  next: "Next", getStarted: "Get started", skip: "Skip", explore: "Explore without account",
  ob1t: "Find parking in seconds", ob1b: "Live availability across Casablanca, Rabat, Marrakech and Tangier.",
  ob2t: "Pay with ParkSpot Wallet", ob2b: "Top up once, book in one tap, get refunds automatically.",
  ob3t: "Your AI parking assistant", ob3b: "Ask anything — from the cheapest spot to EV charging.",
  features: "Features", open24: "Open 24/7", capacity: "Capacity", availability: "Availability", update: "Update",
};
type Dict = typeof en;
const ar: Dict = {
  tagline: "ركن أذكى. رحلات أسهل.",
  home: "الرئيسية", map: "الخريطة", bookings: "الحجوزات", wallet: "المحفظة", profile: "الحساب", assistant: "المساعد",
  hello: "اعثر على مكانك", search: "ابحث عن مدينة أو موقف", nearby: "مواقف قريبة منك",
  perHour: "/ ساعة", spots: "أماكن متاحة", full: "ممتلئ", book: "احجز الآن", details: "التفاصيل",
  signIn: "تسجيل الدخول", signUp: "إنشاء حساب", email: "البريد الإلكتروني", password: "كلمة المرور", name: "الاسم الكامل",
  continueGoogle: "المتابعة عبر Google", or: "أو", haveAccount: "لديك حساب؟", noAccount: "جديد على ParkSpot؟",
  checkEmail: "تحقق من بريدك لتأكيد حسابك ثم سجّل الدخول.",
  signInToContinue: "سجّل الدخول للمتابعة", signInBody: "تحتاج إلى حساب للحجوزات والمحفظة والملف الشخصي.",
  available: "الرصيد المتاح", reserved: "محجوز", deposited: "إجمالي الإيداعات", addMoney: "إضافة رصيد",
  recent: "آخر المعاملات", seeAll: "عرض الكل", noTx: "لا توجد معاملات بعد. أضف رصيداً للبدء.",
  demoNote: "وضع تجريبي — هذا ليس مالاً حقيقياً ولا يتم خصم أي بطاقة.",
  chooseAmount: "اختر المبلغ", custom: "مبلغ مخصص (درهم)", outcome: "نتيجة الدفع التجريبي",
  succeeded: "ناجح", failed: "فشل", pending: "قيد الانتظار", review: "مراجعة", confirmTopup: "تأكيد الشحن",
  topupDone: "تم الشحن بنجاح", topupFailed: "فشل الدفع — لم تتم إضافة أي مبلغ", topupPending: "الدفع قيد الانتظار — لم يُحدَّث الرصيد",
  history: "سجل المعاملات", topup: "شحن", booking_charge: "رسوم ركن", refund: "استرداد",
  reviewPay: "المراجعة والدفع", start: "وقت البدء", duration: "المدة", hours: "ساعات", total: "المبلغ المستحق",
  after: "الرصيد بعد الدفع", payWallet: "الدفع بالمحفظة", insufficient: "رصيد غير كافٍ",
  needMore: "تحتاج إلى {x} إضافية لإتمام الحجز.", confirmed: "تم تأكيد الحجز", accessCode: "رمز الدخول",
  viewBookings: "عرض حجوزاتي", cancel: "إلغاء الحجز", cancelled: "ملغى", active: "نشط",
  noBookings: "لا توجد حجوزات بعد.", refundPolicy: "استرداد كامل حتى ساعتين قبل البدء، 50٪ حتى البدء، ولا شيء بعده.",
  vehicle: "المركبة", plate: "رقم اللوحة", model: "الطراز", phone: "الهاتف", save: "حفظ", saved: "تم الحفظ",
  logout: "تسجيل الخروج", language: "اللغة", ops: "العمليات", askAI: "اسأل عن المواقف أو الأسعار أو حجوزاتك…",
  aiHello: "مرحباً! أنا ParkSpot AI. اسألني أين تركن، عن الأسعار أو عن المحفظة.",
  next: "التالي", getStarted: "ابدأ الآن", skip: "تخطي", explore: "تصفح بدون حساب",
  ob1t: "اعثر على موقف في ثوانٍ", ob1b: "توفر مباشر في الدار البيضاء والرباط ومراكش وطنجة.",
  ob2t: "ادفع بمحفظة ParkSpot", ob2b: "اشحن مرة واحدة، احجز بلمسة، واسترد تلقائياً.",
  ob3t: "مساعدك الذكي للركن", ob3b: "اسأل عن أي شيء — من أرخص موقف إلى شحن السيارات الكهربائية.",
  features: "المزايا", open24: "مفتوح 24/7", capacity: "السعة", availability: "التوفر", update: "تحديث",
};

type Lang = "en" | "ar";
type Ctx = { lang: Lang; dir: "ltr" | "rtl"; setLang: (l: Lang) => void; t: (k: keyof Dict, v?: Record<string, string>) => string };
const I18n = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  useEffect(() => {
    const s = localStorage.getItem("ps-lang");
    if (s === "ar" || s === "en") setLangState(s);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const setLang = (l: Lang) => { localStorage.setItem("ps-lang", l); setLangState(l); };
  const t = (k: keyof Dict, v?: Record<string, string>) => {
    let s = (lang === "ar" ? ar : en)[k];
    if (v) for (const [a, b] of Object.entries(v)) s = s.replace(`{${a}}`, b);
    return s;
  };
  return <I18n.Provider value={{ lang, dir: lang === "ar" ? "rtl" : "ltr", setLang, t }}>{children}</I18n.Provider>;
}
export function useI18n() {
  const c = useContext(I18n);
  if (!c) throw new Error("I18nProvider missing");
  return c;
}
