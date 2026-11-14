import clsx from "clsx";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Languages,
  Loader2,
  Mic,
  Minus,
  Send,
  ShoppingBag,
  Sparkles,
  Trash2,
  UtensilsCrossed,
  Volume2,
  VolumeX,
  X
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, SelectField, TextField, useToast } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { money } from "../lib/format";
import { quickKioskPrompts, useI18n } from "../lib/i18n";
import type { KioskCartLine, KioskChatResponse, KioskSession, KioskSuggestion, Order } from "../lib/types";

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  text: string;
}

/* ------------------------------------------------------------------ */
/* Minimal Web Speech API typings (STT is not in TypeScript's lib.dom) */
/* ------------------------------------------------------------------ */
interface SpeechResultEventLike {
  resultIndex: number;
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult: ((event: SpeechResultEventLike) => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function speechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const PAYMENT_OPTIONS = [
  { code: "cash", en: "Cash at counter", ar: "كاش عند الكاشير" },
  { code: "card", en: "Card at counter", ar: "بطاقة عند الكاشير" }
];

function nextId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Kiosk() {
  const { t, lang, setLang, pick } = useI18n();
  const toast = useToast();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [cart, setCart] = useState<KioskCartLine[]>([]);
  const [subtotal, setSubtotal] = useState(0);
  const [suggestions, setSuggestions] = useState<KioskSuggestion[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const [listening, setListening] = useState(false);
  const [speechSupported] = useState(() => speechRecognitionCtor() !== null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [confirmed, setConfirmed] = useState<Order | null>(null);
  const [clearing, setClearing] = useState(false);

  const endRef = useRef<HTMLDivElement | null>(null);
  const cartRef = useRef<KioskCartLine[]>([]);
  const bootingRef = useRef(false);
  const speakRef = useRef<(text: string) => void>(() => undefined);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  cartRef.current = cart;

  useEffect(() => {
    speakRef.current = (text: string) => {
      if (!voiceOn || typeof window === "undefined" || !("speechSynthesis" in window)) return;
      try {
        const synth = window.speechSynthesis;
        synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang === "ar" ? "ar-EG" : "en-US";
        utterance.rate = 0.98;
        const voice = synth
          .getVoices()
          .find((candidate) => candidate.lang.toLowerCase().startsWith(lang === "ar" ? "ar" : "en"));
        if (voice) utterance.voice = voice;
        synth.speak(utterance);
      } catch {
        /* speech synthesis is a progressive enhancement */
      }
    };
  }, [voiceOn, lang]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  const toggleListening = useCallback(() => {
    if (!sessionId || booting) return;
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const Ctor = speechRecognitionCtor();
    if (!Ctor) {
      toast.error(
        pick(
          "Voice input is not supported in this browser. Please type your order.",
          "إدخال الصوت غير مدعوم في هذا المتصفح. من فضلك اكتب طلبك."
        )
      );
      return;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    const recognition = new Ctor();
    recognition.lang = lang === "ar" ? "ar-EG" : "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);
    recognition.onerror = (event) => {
      setListening(false);
      if (event.error === "aborted") return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        toast.error(
          pick(
            "Microphone permission was blocked. Allow it in the browser or type your order.",
            "تم رفض إذن الميكروفون. اسمح به من المتصفح أو اكتب طلبك."
          )
        );
      } else if (event.error === "no-speech") {
        toast.error(pick("I did not hear anything. Please try again.", "مسمعتش حاجة. جرّب تاني."));
      } else {
        toast.error(
          pick(
            "Voice input failed. You can type your order instead.",
            "تعذر إدخال الصوت. ممكن تكتب طلبك بدلًا من ذلك."
          )
        );
      }
    };
    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i += 1) {
        transcript += event.results[i][0]?.transcript ?? "";
      }
      if (transcript.trim()) setInput(transcript.trim());
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      setListening(false);
      toast.error(
        pick(
          "Voice input could not start. Please type your order.",
          "تعذر بدء إدخال الصوت. من فضلك اكتب طلبك."
        )
      );
    }
  }, [booting, lang, listening, pick, sessionId, toast]);

  const startSession = useCallback(async () => {
    setBooting(true);
    setBootError(null);
    try {
      const data = await api<KioskSession>("/ai/kiosk/session", {
        method: "POST",
        body: { language: lang }
      });
      setSessionId(data.session_id);
      setCart([]);
      setSubtotal(0);
      setSuggestions([]);
      setConfirmed(null);
      setConfirmOpen(false);
      const greeting = t("kiosk.greeting");
      setMessages([{ id: nextId(), role: "assistant", text: greeting }]);
      speakRef.current(greeting);
    } catch (err) {
      setBootError(errorMessage(err));
    } finally {
      setBooting(false);
    }
  }, [lang, t]);

  // Create a fresh session on first load. A language switch while the cart is
  // empty also restarts the conversation; a cart in progress is preserved.
  useEffect(() => {
    if (cartRef.current.length > 0 && sessionId) return;
    // React StrictMode invokes effects twice in development. Without this
    // guard the kiosk creates two sessions and can leave an orphaned one.
    if (bootingRef.current) return;
    bootingRef.current = true;
    void startSession().finally(() => {
      bootingRef.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const send = useCallback(
    async (raw?: string) => {
      const text = (raw ?? input).trim();
      if (!text || !sessionId || sending) return;
      setInput("");
      setSending(true);
      setMessages((prev) => [...prev, { id: nextId(), role: "user", text }]);
      try {
        const data = await api<KioskChatResponse>("/ai/kiosk/chat", {
          method: "POST",
          body: { session_id: sessionId, message: text, language: lang }
        });
        setMessages((prev) => [...prev, { id: nextId(), role: "assistant", text: data.reply }]);
        setCart(data.cart ?? []);
        setSubtotal(Number(data.subtotal ?? 0));
        setSuggestions(data.suggestions ?? []);
        speakRef.current(data.reply);
      } catch (err) {
        const message = errorMessage(err);
        toast.error(message);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            text: pick(
              "Sorry, I could not reach the kitchen system. Please try again.",
              "معلش، مقدرتش أوصل لنظام المطبخ. جرّب تاني."
            )
          }
        ]);
      } finally {
        setSending(false);
      }
    },
    [input, lang, pick, sending, sessionId, toast]
  );

  const clearCart = async () => {
    if (!sessionId) return;
    setClearing(true);
    try {
      await api("/ai/kiosk/reset", { method: "POST", body: { session_id: sessionId, message: "reset", language: lang } });
      setCart([]);
      setSubtotal(0);
      toast.push(pick("Order cleared", "تم تفريغ الطلب"));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setClearing(false);
    }
  };

  const confirmOrder = async () => {
    if (!sessionId) return;
    setConfirming(true);
    try {
      const data = await api<{ message: string; order: Order; summary: unknown }>("/ai/kiosk/confirm", {
        method: "POST",
        body: {
          session_id: sessionId,
          customer_name: customerName || undefined,
          customer_phone: customerPhone || undefined,
          payment_method: paymentMethod
        }
      });
      setConfirmed(data.order);
      setCart([]);
      setSubtotal(0);
      setSuggestions([]);
      setConfirmOpen(false);
      speakRef.current(
        pick(
          `Order confirmed. Your order number is ${data.order.order_id}. Please pay at the counter.`,
          `تم تأكيد الطلب. رقم طلبك ${data.order.order_id}. من فضلك ادفع عند الكاشير.`
        )
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setConfirming(false);
    }
  };

  const greetingSuggestions = quickKioskPrompts[lang];

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-ink-900 text-white">
      <div className="pointer-events-none absolute -top-32 -end-24 h-[420px] w-[420px] rounded-full bg-brand-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -start-24 h-[380px] w-[380px] rounded-full bg-sky-500/10 blur-3xl" />

      <header className="relative z-10 flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-8">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500 text-white shadow-lg shadow-brand-900/30">
            <UtensilsCrossed className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <p className="font-display text-base font-extrabold">
              RestoMate <span className="text-brand-400">AI</span>
            </p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/40">
              {pick("Self-service kiosk", "كشك الخدمة الذاتية")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setVoiceOn((prev) => !prev)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition",
              voiceOn
                ? "border-brand-400/40 bg-brand-500/20 text-brand-200"
                : "border-white/15 text-white/60 hover:bg-white/10"
            )}
            aria-pressed={voiceOn}
          >
            {voiceOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            <span className="hidden sm:inline">{voiceOn ? t("kiosk.voiceOn") : t("kiosk.voiceOff")}</span>
          </button>
          <button
            onClick={() => setLang(lang === "en" ? "ar" : "en")}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 px-3 py-2 text-xs font-bold text-white/70 transition hover:bg-white/10"
          >
            <Languages className="h-4 w-4" />
            {t("common.language")}
          </button>
          <a
            href="/"
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 px-3 py-2 text-xs font-bold text-white/60 transition hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
            <span className="hidden sm:inline">{t("kiosk.exit")}</span>
          </a>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-7xl flex-1 flex-col gap-5 px-4 py-5 sm:px-6 lg:flex-row lg:gap-6 lg:px-8 lg:py-7">
        <section className="flex min-h-[52vh] flex-1 flex-col overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] shadow-2xl backdrop-blur">
          <div className="flex items-center gap-4 border-b border-white/10 px-5 py-4">
            <div className="relative grid h-14 w-14 shrink-0 place-items-center rounded-full bg-brand-500 text-white">
              <span className="absolute inset-0 animate-ping rounded-full bg-brand-500/30" />
              <Bot className="relative h-7 w-7" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-display text-base font-bold">{pick("RestoMate assistant", "مساعد ريستوميت")}</p>
              <p className="inline-flex items-center gap-1.5 text-xs text-white/50">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-emerald-400" />
                {pick("Ready to take your order", "جاهز يستقبل طلبك")}
              </p>
            </div>
            <Sparkles className="hidden h-5 w-5 text-brand-300 sm:block" />
          </div>

          <div className="scroll-thin flex-1 space-y-3 overflow-y-auto px-4 py-4 sm:px-5">
            {booting ? (
              <div className="flex h-full items-center justify-center gap-2 text-sm text-white/50">
                <Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}
              </div>
            ) : bootError ? (
              <div className="m-auto max-w-sm rounded-2xl border border-rose-400/30 bg-rose-500/10 p-5 text-center text-sm text-rose-100">
                <p>{bootError}</p>
                <Button className="mt-3" size="sm" onClick={() => void startSession()}>
                  {t("common.retry")}
                </Button>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={clsx("flex", message.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div
                    className={clsx(
                      "max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
                      message.role === "user"
                        ? "rounded-br-md bg-brand-500 text-white"
                        : "rounded-bl-md border border-white/10 bg-white text-ink-800"
                    )}
                  >
                    {message.text}
                  </div>
                </div>
              ))
            )}
            {sending ? (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md border border-white/10 bg-white/90 px-4 py-2.5 text-sm text-ink-500">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-.2s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500 [animation-delay:-.1s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500" />
                </div>
              </div>
            ) : null}
            <div ref={endRef} />
          </div>

          <div className="border-t border-white/10 px-3 pb-3 pt-3 sm:px-5 sm:pb-4">
            {suggestions.length ? (
              <div className="mb-2 flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                {suggestions.slice(0, 5).map((item) => (
                  <button
                    key={item.item_id}
                    onClick={() =>
                      void send(
                        lang === "ar" ? `بكام ${item.item_name_ar || item.item_name}؟` : `How much is ${item.item_name}?`
                      )
                    }
                    className="shrink-0 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-white/75 transition hover:bg-white/15"
                  >
                    {pick(item.item_name, item.item_name_ar || item.item_name)} · {money(item.price)}
                  </button>
                ))}
              </div>
            ) : messages.length <= 1 ? (
              <div className="mb-2 flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                {greetingSuggestions.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => void send(prompt)}
                    className="shrink-0 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-white/75 transition hover:bg-white/15"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            ) : null}

            <form
              className="flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void send();
              }}
            >
              <div className="relative flex-1">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder={
                    listening
                      ? pick("Listening… speak now", "بسمعك… اتكلم دلوقتي")
                      : t("kiosk.placeholder")
                  }
                  maxLength={1000}
                  disabled={!sessionId || booting}
                  className={clsx(
                    "h-12 w-full rounded-2xl border border-white/15 bg-white/95 ps-3 text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-500/20 disabled:opacity-60",
                    speechSupported ? "pe-11" : "pe-3"
                  )}
                />
                {speechSupported ? (
                  <button
                    type="button"
                    onClick={toggleListening}
                    disabled={!sessionId || booting}
                    aria-label={pick("Start voice input", "ابدأ إدخال الصوت")}
                    aria-pressed={listening}
                    title={
                      listening
                        ? pick("Stop listening", "إيقاف الاستماع")
                        : pick("Speak your order", "اتكلم طلبك")
                    }
                    className={clsx(
                      "absolute end-1.5 top-1/2 -translate-y-1/2 rounded-xl p-2 transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/30 disabled:opacity-40",
                      listening
                        ? "animate-pulse bg-rose-500 text-white"
                        : "text-ink-400 hover:bg-ink-100 hover:text-brand-600"
                    )}
                  >
                    <Mic className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
              <Button type="submit" size="icon" className="h-12 w-12 rounded-2xl" loading={sending} disabled={!input.trim() || !sessionId}>
                <Send className="h-5 w-5" />
              </Button>
            </form>
            <p className="mt-2 text-center text-[11px] text-white/35">{t("kiosk.confirmHint")}</p>
          </div>
        </section>

        <aside className="flex w-full flex-col gap-4 lg:w-[380px] lg:shrink-0">
          {confirmed ? (
            <div className="rounded-3xl border border-emerald-400/25 bg-emerald-500/10 p-6 text-center shadow-2xl">
              <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-500 text-white">
                <CheckCircle2 className="h-8 w-8" />
              </span>
              <h2 className="mt-4 font-display text-xl font-extrabold">{t("kiosk.success")}</h2>
              <p className="mt-1 text-sm text-emerald-100/80">{t("kiosk.successBody")}</p>
              <div className="mt-4 rounded-2xl border border-white/10 bg-ink-900/40 px-4 py-3">
                <p className="text-[11px] font-bold uppercase tracking-wider text-white/45">{t("kiosk.orderNumber")}</p>
                <p className="font-display text-3xl font-extrabold text-white">#{confirmed.order_id}</p>
                <p className="mt-1 text-sm text-white/60">{money(confirmed.total_amount)}</p>
              </div>
              <Button className="mt-4 w-full" onClick={() => void startSession()}>
                <ArrowRight className="h-4 w-4" /> {t("kiosk.newOrder")}
              </Button>
            </div>
          ) : (
            <div className="flex flex-1 flex-col rounded-3xl border border-white/10 bg-white text-ink-900 shadow-2xl">
              <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-700">
                    <ShoppingBag className="h-4.5 w-4.5" />
                  </span>
                  <div>
                    <p className="font-display text-base font-bold">{t("kiosk.cart")}</p>
                    <p className="text-[11px] text-ink-400">
                      {cart.reduce((sum, line) => sum + line.quantity, 0)} {t("common.items")}
                    </p>
                  </div>
                </div>
                {cart.length ? (
                  <button
                    onClick={() => void clearCart()}
                    disabled={clearing}
                    className="rounded-lg p-2 text-ink-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40"
                    title={t("menu.clear")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                ) : null}
              </div>

              <div className="scroll-thin flex-1 space-y-3 px-5 py-4">
                {cart.length === 0 ? (
                  <div className="flex h-full min-h-[160px] flex-col items-center justify-center text-center">
                    <ShoppingBag className="h-9 w-9 text-ink-200" />
                    <p className="mt-3 text-sm text-ink-500">{t("kiosk.emptyCart")}</p>
                    <p className="mt-1 text-xs text-ink-400">
                      {pick("Try “two OG burgers and a mojito”.", "جرّب «اتنين أو جي برجر وموهيتو».")}
                    </p>
                  </div>
                ) : (
                  cart.map((line) => (
                    <div key={line.item_id} className="flex items-start gap-3 rounded-xl border border-ink-100 bg-ink-50/60 px-3 py-2.5">
                      <span className="grid h-6 min-w-6 place-items-center rounded-lg bg-white text-xs font-extrabold text-brand-700 ring-1 ring-ink-100">
                        {line.quantity}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink-800">
                          {pick(line.item_name, line.item_name_ar || line.item_name)}
                        </p>
                        <p className="text-[11px] text-ink-400">{money(line.unit_price)}</p>
                      </div>
                      <p className="text-sm font-bold text-ink-800">{money(line.line_total)}</p>
                    </div>
                  ))
                )}
              </div>

              <div className="border-t border-ink-100 px-5 py-4">
                <div className="flex items-center justify-between text-sm text-ink-500">
                  <span>{t("common.subtotal")}</span>
                  <span className="font-display text-xl font-extrabold text-ink-900">{money(subtotal)}</span>
                </div>
                <Button
                  className="mt-3 w-full"
                  size="lg"
                  disabled={!cart.length}
                  onClick={() => setConfirmOpen(true)}
                >
                  <CheckCircle2 className="h-5 w-5" /> {t("kiosk.confirm")}
                </Button>
                <p className="mt-2 text-center text-[11px] text-ink-400">{t("kiosk.confirmHint")}</p>
              </div>
            </div>
          )}
        </aside>
      </main>

      {confirmOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-900/70 p-0 backdrop-blur-sm sm:items-center sm:p-6">
          <div className="w-full max-w-lg rounded-t-3xl bg-white p-5 text-ink-900 shadow-2xl sm:rounded-3xl sm:p-6">
            <div className="mb-3 flex items-start justify-between">
              <div>
                <h2 className="font-display text-xl font-extrabold">{t("kiosk.confirm")}</h2>
                <p className="mt-0.5 text-sm text-ink-500">{t("kiosk.confirmHint")}</p>
              </div>
              <button
                className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100"
                onClick={() => setConfirmOpen(false)}
                aria-label={t("common.close")}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mb-4 max-h-44 space-y-2 overflow-y-auto rounded-xl bg-ink-50 p-3">
              {cart.map((line) => (
                <div key={line.item_id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-ink-700">
                    <Minus className="me-1 inline h-3 w-3 text-ink-300" />
                    {line.quantity}× {pick(line.item_name, line.item_name_ar || line.item_name)}
                  </span>
                  <span className="font-semibold">{money(line.line_total)}</span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-ink-200 pt-2 text-sm font-bold">
                <span>{t("common.total")}</span>
                <span>{money(subtotal)}</span>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label={t("kiosk.yourName")}
                value={customerName}
                onChange={(event) => setCustomerName(event.target.value)}
                maxLength={120}
                placeholder={pick("e.g. Nour", "مثال: نور")}
              />
              <TextField
                label={t("kiosk.yourPhone")}
                value={customerPhone}
                onChange={(event) => setCustomerPhone(event.target.value)}
                maxLength={30}
                placeholder="010…"
                inputMode="tel"
              />
              <div className="sm:col-span-2">
                <SelectField
                  label={t("menu.paymentMethod")}
                  value={paymentMethod}
                  onChange={(event) => setPaymentMethod(event.target.value)}
                >
                  {PAYMENT_OPTIONS.map((option) => (
                    <option key={option.code} value={option.code}>
                      {pick(option.en, option.ar)}
                    </option>
                  ))}
                </SelectField>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button loading={confirming} onClick={() => void confirmOrder()}>
                <CheckCircle2 className="h-4 w-4" /> {t("common.confirm")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
