import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const en = {
  tagline: "Smarter Parking. Easier Journeys.",
  home: "Home", map: "Map", bookings: "Bookings", wallet: "Wallet", profile: "Profile", assistant: "Assistant",
  hello: "Find your spot", search: "Search city or facility", nearby: "Parking near you",
  perHour: "/ hr", spots: "spots left", full: "Full", book: "Book now", details: "Details",
  signIn: "Sign in", signUp: "Create account", email: "Email", password: "Password", name: "Full name",
  continueGoogle: "Continue with Google", or: "or", haveAccount: "Already have an account?", noAccount: "New to ParkSpot?",
  checkEmail: "Check your email to confirm your account, then sign in.",
  invalidCredentials: "Invalid email or password. Check both and try again.",
  accountExists: "An account with this email already exists. Sign in instead.",
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
  suggest1: "Cheapest parking in Casablanca?", suggest2: "Where can I charge my EV?", suggest3: "How do refunds work?",
  aiUnavailable: "AI assistant is unavailable right now. Manual search on Home still works.",
  realAvailability: "Live availability from ParkSpot inventory",
  mic: "Voice input", listening: "Listening… tap to stop", voiceUnsupported: "Voice input is not enabled.",
  visionTitle: "Camera verification (SAM 3.1 + OCR)", visionBody: "SAM locates vehicles and plates; OCR reads the plate; access is granted only when a real booking matches.",
  cameraReal: "Real camera frame", cameraSim: "Simulated camera (demo image)", analyzeFrame: "Analyze frame",
  uploadFrame: "Upload a frame", vehiclesDetected: "Vehicles detected", plateRead: "Plate", plateNotRead: "Plate not read confidently",
  ocrConfidence: "OCR confidence", accessVerified: "Booking verified", accessNotGranted: "Access not granted",
  visionUnavailable: "Vision backend not configured. Set SAM_SERVICE_URL on the server (see README).",
  voiceSearch: "Voice Search", parkingNearMe: "Parking Near Me", nearYourLocation: "Near your location",
  locationNeeded: "ParkSpot uses your location only to find parking near you. It is never stored or tracked.",
  locationDenied: "Location permission denied. You can still search manually above.",
  locationUnavailable: "Your location is temporarily unavailable. Try again or search manually.",
  locationTimeout: "Getting your location timed out. Try again.",
  locationUnsupported: "Location is not available in this browser. Search manually instead.",
  noNearby: "No parking found within {x}.", widenSearch: "Widen search",
  recording: "Recording…", stopRecording: "Stop", cancel: "Cancel", transcribing: "Transcribing…",
  away: "{x} away",
  voiceBackendMissing: "Voice backend not connected. Start the FastAPI backend and set VITE_META_API_URL for the frontend.",
  voiceServerOff: "Voice is off on the server. Set MUSE_VOICE_ENABLED=true and MODEL_API_KEY in the backend .env, then restart the backend.",
  voiceKeyMissing: "Voice key missing on the server. Set MODEL_API_KEY in the backend .env, then restart the backend.",
  locationInsecure: "Location needs a secure connection (HTTPS or localhost). Open the app via localhost or HTTPS to use this.",
  micInsecure: "Microphone needs a secure connection (HTTPS or localhost). Open the app via localhost or HTTPS to use voice search.",
  adminTitle: "Super Admin", adminRestricted: "Restricted to administrators.",
  aOverview: "Overview", aUsers: "Users & Accounts", aFacilities: "Parking Facilities", aBookings: "Bookings",
  aPricing: "Pricing", aAI: "AI Management", aCameras: "Cameras & Access", aPayments: "Payments & Wallet",
  aReports: "Reports", aIncidents: "Notifications", aAudit: "Audit Logs", aSettings: "System Settings",
  totalDrivers: "Total drivers", suspendedUsers: "Suspended", totalFacilitiesLbl: "Facilities", authorizedSpaces: "Authorized spaces",
  availableSpaces: "Available spaces", activeBookings: "Active reservations", camerasLbl: "Cameras", revenueDemo: "Revenue (DEMO)",
  searchLbl: "Search", reasonLbl: "Reason (required)", confirmAction: "Confirm", actionsLbl: "Actions",
  suspend: "Suspend", reactivate: "Reactivate", grantRole: "Grant", revokeRole: "Revoke",
  roleAdmin: "Admin", rolePartner: "Partner", roleUser: "Driver",
  healthCheck: "Health check", configuredLbl: "Configured", reachableLbl: "Reachable", testedOk: "Responding",
  enabledLbl: "Enabled", disabledLbl: "Disabled", notInstalled: "Not installed", sinceRestart: "since backend restart",
  exportCsv: "Export CSV", demoBanner: "DEMO payments — simulated wallet, not real money.",
  adjustBalance: "Adjust balance", amountCents: "Amount (cents, +/-)", priceCents: "Price (cents/hour)",
  totalCapacityLbl: "Total capacity", authorizedCapacityLbl: "Authorized capacity", newFacility: "New facility",
  createLbl: "Create", incidentStatus: "Status", openLbl: "Open", resolvedLbl: "Resolved",
  saveSettings: "Save settings", refreshLbl: "Refresh", noData: "Nothing here yet.",
  bookingsPerDay: "Bookings per day", statusDistribution: "Reservation status", recentActivity: "Recent administrative activity",
  backendOff: "Admin backend unreachable. Start the FastAPI backend and set VITE_META_API_URL.",
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
  invalidCredentials: "البريد الإلكتروني أو كلمة المرور غير صحيحة. تحقق وحاول من جديد.",
  accountExists: "يوجد حساب بهذا البريد الإلكتروني. سجّل الدخول بدلاً من ذلك.",
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
  suggest1: "أرخص موقف في الدار البيضاء؟", suggest2: "أين يمكنني شحن سيارتي الكهربائية؟", suggest3: "كيف يعمل الاسترداد؟",
  aiUnavailable: "المساعد الذكي غير متاح حالياً. البحث اليدوي في الرئيسية يعمل دائماً.",
  realAvailability: "توفر مباشر من مخزون ParkSpot",
  mic: "إدخال صوتي", listening: "جارٍ الاستماع… اضغط للإيقاف", voiceUnsupported: "الإدخال الصوتي غير مفعّل.",
  visionTitle: "التحقق بالكاميرا (SAM 3.1 + OCR)", visionBody: "يحدد SAM المركبات واللوحات؛ يقرأ OCR اللوحة؛ ولا يُمنح الدخول إلا عند تطابق حجز حقيقي.",
  cameraReal: "إطار كاميرا حقيقي", cameraSim: "كاميرا محاكاة (صورة تجريبية)", analyzeFrame: "تحليل الإطار",
  uploadFrame: "رفع إطار", vehiclesDetected: "المركبات المكتشفة", plateRead: "اللوحة", plateNotRead: "لم تُقرأ اللوحة بثقة كافية",
  ocrConfidence: "ثقة OCR", accessVerified: "تم التحقق من الحجز", accessNotGranted: "لم يُمنح الدخول",
  visionUnavailable: "خدمة الرؤية غير مهيأة. عيّن SAM_SERVICE_URL على الخادم (راجع README).",
  voiceSearch: "البحث الصوتي", parkingNearMe: "مواقف قربي", nearYourLocation: "قرب موقعك",
  locationNeeded: "يستخدم ParkSpot موقعك فقط للعثور على مواقف قريبة منك. لا يُحفظ ولا يُتتبع أبداً.",
  locationDenied: "تم رفض إذن الموقع. يمكنك البحث يدوياً أعلاه.",
  locationUnavailable: "موقعك غير متاح مؤقتاً. حاول مجدداً أو ابحث يدوياً.",
  locationTimeout: "انتهت مهلة تحديد موقعك. حاول مجدداً.",
  locationUnsupported: "الموقع غير متاح في هذا المتصفح. ابحث يدوياً بدلاً من ذلك.",
  noNearby: "لم يتم العثور على مواقف ضمن {x}.", widenSearch: "توسيع البحث",
  recording: "جارٍ التسجيل…", stopRecording: "إيقاف", cancel: "إلغاء", transcribing: "جارٍ التفريغ…",
  away: "على بعد {x}",
  voiceBackendMissing: "خادم الصوت غير متصل. شغّل خادم FastAPI وعيّن VITE_META_API_URL للواجهة.",
  voiceServerOff: "الصوت متوقف على الخادم. عيّن MUSE_VOICE_ENABLED=true و MODEL_API_KEY في ملف .env الخاص بالخادم ثم أعد تشغيله.",
  voiceKeyMissing: "مفتاح الصوت مفقود على الخادم. عيّن MODEL_API_KEY في ملف .env الخاص بالخادم ثم أعد تشغيله.",
  locationInsecure: "يتطلب الموقع اتصالاً آمناً (HTTPS أو localhost). افتح التطبيق عبر localhost أو HTTPS لاستخدام هذا.",
  micInsecure: "يتطلب الميكروفون اتصالاً آمناً (HTTPS أو localhost). افتح التطبيق عبر localhost أو HTTPS لاستخدام البحث الصوتي.",
  adminTitle: "المشرف العام", adminRestricted: "مقتصر على المشرفين.",
  aOverview: "نظرة عامة", aUsers: "المستخدمون والحسابات", aFacilities: "مواقف السيارات", aBookings: "الحجوزات",
  aPricing: "التسعير", aAI: "إدارة الذكاء الاصطناعي", aCameras: "الكاميرات والدخول", aPayments: "المدفوعات والمحفظة",
  aReports: "التقارير", aIncidents: "الإشعارات", aAudit: "سجلات التدقيق", aSettings: "إعدادات النظام",
  totalDrivers: "إجمالي السائقين", suspendedUsers: "موقوفون", totalFacilitiesLbl: "المنشآت", authorizedSpaces: "الأماكن المصرّح بها",
  availableSpaces: "الأماكن المتاحة", activeBookings: "الحجوزات النشطة", camerasLbl: "الكاميرات", revenueDemo: "الإيرادات (تجريبي)",
  searchLbl: "بحث", reasonLbl: "السبب (مطلوب)", confirmAction: "تأكيد", actionsLbl: "إجراءات",
  suspend: "إيقاف", reactivate: "إعادة تفعيل", grantRole: "منح", revokeRole: "سحب",
  roleAdmin: "مشرف", rolePartner: "شريك", roleUser: "سائق",
  healthCheck: "فحص الصحة", configuredLbl: "مهيأ", reachableLbl: "قابل للوصول", testedOk: "يستجيب",
  enabledLbl: "مفعّل", disabledLbl: "معطّل", notInstalled: "غير مثبّت", sinceRestart: "منذ إعادة تشغيل الخادم",
  exportCsv: "تصدير CSV", demoBanner: "مدفوعات تجريبية — محفظة محاكاة، ليست أموالاً حقيقية.",
  adjustBalance: "تعديل الرصيد", amountCents: "المبلغ (سنتيم، +/-)", priceCents: "السعر (سنتيم/ساعة)",
  totalCapacityLbl: "السعة الإجمالية", authorizedCapacityLbl: "السعة المصرّح بها", newFacility: "منشأة جديدة",
  createLbl: "إنشاء", incidentStatus: "الحالة", openLbl: "مفتوح", resolvedLbl: "تم الحل",
  saveSettings: "حفظ الإعدادات", refreshLbl: "تحديث", noData: "لا شيء هنا بعد.",
  bookingsPerDay: "الحجوزات يومياً", statusDistribution: "حالة الحجوزات", recentActivity: "أحدث نشاط إداري",
  backendOff: "خادم الإدارة غير متاح. شغّل خادم FastAPI وعيّن VITE_META_API_URL.",
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
