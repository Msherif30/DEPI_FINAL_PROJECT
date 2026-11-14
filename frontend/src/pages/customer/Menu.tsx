import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  BadgeCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Flame,
  Minus,
  Plus,
  Search,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Star,
  Trash2,
  UtensilsCrossed,
  X
} from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Loading, Modal, PageHeader, SelectField, TextAreaField, useToast } from "../../components/ui";
import { api, errorMessage, qs } from "../../lib/api";
import { useCart } from "../../lib/cart";
import { money } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Category, MenuItem, Order, Paginated, PaymentMethod } from "../../lib/types";

interface MenuResponse extends Paginated<MenuItem> {
  pages: number;
}

export default function Menu() {
  const { t, lang, pick } = useI18n();
  const { lines, subtotal, count, add, setQuantity, remove, clear } = useCart();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [category, setCategory] = useState<number | "">("");
  const [sort, setSort] = useState("name");
  const [availableOnly, setAvailableOnly] = useState(false);
  const [featured, setFeatured] = useState(false);
  const [page, setPage] = useState(1);
  const [mobileCart, setMobileCart] = useState(false);

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/menu/categories")
  });

  const menu = useQuery({
    queryKey: ["menu", deferredSearch, category, sort, availableOnly, featured, page],
    queryFn: () =>
      api<MenuResponse>(
        `/menu${qs({
          q: deferredSearch || undefined,
          category_id: category || undefined,
          sort,
          available_only: availableOnly || undefined,
          featured: featured || undefined,
          page,
          page_size: 24
        })}`
      )
  });

  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () => api<PaymentMethod[]>("/menu/payment-methods")
  });

  const cartMap = useMemo(() => new Map(lines.map((line) => [line.item_id, line.quantity])), [lines]);

  const resetPage = () => setPage(1);

  const addItem = (item: MenuItem) => {
    add(
      {
        item_id: item.item_id,
        item_name: item.item_name,
        item_name_ar: item.item_name_ar,
        price: Number(item.price)
      },
      1
    );
    toast.success(`${pick(item.item_name, item.item_name_ar)} · ${t("menu.added")}`);
  };

  return (
    <div>
      <PageHeader
        eyebrow={t("app.name")}
        title={t("menu.title")}
        subtitle={t("menu.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="relative">
              <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  resetPage();
                }}
                placeholder={`${t("common.search")}…`}
                className="field h-10 w-56 ps-9"
              />
            </label>
            <SelectField value={sort} onChange={(event) => setSort(event.target.value)} className="h-10 w-40">
              <option value="name">{pick("Name", "الاسم")}</option>
              <option value="price_asc">{pick("Price ↑", "السعر ↑")}</option>
              <option value="price_desc">{pick("Price ↓", "السعر ↓")}</option>
              <option value="newest">{pick("Newest", "الأحدث")}</option>
            </SelectField>
          </div>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <button
          onClick={() => {
            setCategory("");
            resetPage();
          }}
          className={clsx(
            "rounded-full border px-4 py-2 text-sm font-semibold transition",
            category === "" ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 bg-white text-ink-600 hover:border-ink-300"
          )}
        >
          {t("common.all")} <span className="opacity-60">({categories.data?.length ?? 0})</span>
        </button>
        {(categories.data ?? []).map((cat) => (
          <button
            key={cat.category_id}
            onClick={() => {
              setCategory(cat.category_id);
              resetPage();
            }}
            className={clsx(
              "rounded-full border px-4 py-2 text-sm font-semibold transition",
              category === cat.category_id
                ? "border-brand-500 bg-brand-50 text-brand-800"
                : "border-ink-200 bg-white text-ink-600 hover:border-ink-300"
            )}
          >
            {pick(cat.category_name, cat.category_name_ar)}
            <span className="ms-1 opacity-50">{cat.item_count}</span>
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => {
            setFeatured((prev) => !prev);
            resetPage();
          }}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-bold transition",
            featured ? "border-amber-300 bg-amber-50 text-amber-800" : "border-ink-200 bg-white text-ink-600"
          )}
        >
          <Star className="h-3.5 w-3.5" /> {t("menu.featured")}
        </button>
        <button
          onClick={() => {
            setAvailableOnly((prev) => !prev);
            resetPage();
          }}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-bold transition",
            availableOnly ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-ink-200 bg-white text-ink-600"
          )}
        >
          <BadgeCheck className="h-3.5 w-3.5" /> {t("menu.availableOnly")}
        </button>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          {menu.isLoading ? (
            <Loading />
          ) : menu.isError ? (
            <EmptyState title={t("error.generic")} description={errorMessage(menu.error)} action={<Button onClick={() => void menu.refetch()}>{t("common.retry")}</Button>} />
          ) : !menu.data?.items.length ? (
            <EmptyState
              title={pick("No dishes match your filters", "لا توجد أطباق مطابقة")}
              description={pick("Try a different search or category.", "جرّب بحثاً أو فئة مختلفة.")}
              icon={<UtensilsCrossed className="h-6 w-6" />}
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch("");
                    setCategory("");
                    setFeatured(false);
                    setAvailableOnly(false);
                  }}
                >
                  {pick("Reset filters", "إعادة تعيين الفلاتر")}
                </Button>
              }
            />
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {menu.data.items.map((item, index) => {
                  const quantity = cartMap.get(item.item_id) ?? 0;
                  const gradient = [
                    "from-amber-100 via-orange-50 to-white",
                    "from-rose-100 via-orange-50 to-white",
                    "from-emerald-100 via-lime-50 to-white",
                    "from-sky-100 via-indigo-50 to-white",
                    "from-violet-100 via-fuchsia-50 to-white"
                  ][index % 5];
                  return (
                    <Card key={item.item_id} className="group overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg">
                      <div className={clsx("relative flex h-36 items-center justify-center bg-gradient-to-br", gradient)}>
                        {item.image_url ? (
                          <img src={item.image_url} alt={item.item_name} className="h-full w-full object-cover" />
                        ) : (
                          <span className="font-display text-3xl font-extrabold text-ink-900/15">
                            {pick(item.item_name, item.item_name_ar).slice(0, 18)}
                          </span>
                        )}
                        <div className="absolute start-3 top-3 flex gap-1.5">
                          {item.is_featured ? (
                            <Badge tone="warn">
                              <Star className="h-3 w-3" /> {t("menu.featured")}
                            </Badge>
                          ) : null}
                          {!item.is_available ? <Badge tone="danger">{pick("Unavailable", "غير متوفر")}</Badge> : null}
                        </div>
                      </div>
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h3 className="truncate font-display text-sm font-bold text-ink-900">{pick(item.item_name, item.item_name_ar)}</h3>
                            <p className="mt-0.5 text-[11px] text-ink-400">{pick(item.category_name, item.category_name_ar)}</p>
                          </div>
                          <p className="shrink-0 font-display text-sm font-extrabold text-brand-700">{money(item.price)}</p>
                        </div>
                        <p className="mt-2 line-clamp-2 min-h-[32px] text-xs leading-relaxed text-ink-500">
                          {pick(item.description, item.description_ar) || pick("Freshly prepared to order.", "يُحضّر طازجاً عند الطلب.")}
                        </p>
                        <div className="mt-3 flex items-center justify-between">
                          <span className="inline-flex items-center gap-1 text-[11px] text-ink-400">
                            <Clock3 className="h-3.5 w-3.5" /> {item.preparation_time ?? 15} {t("common.min")}
                          </span>
                          {quantity > 0 ? (
                            <div className="flex items-center gap-1 rounded-lg border border-ink-200 p-0.5">
                              <button className="grid h-7 w-7 place-items-center rounded-md hover:bg-ink-100" onClick={() => setQuantity(item.item_id, quantity - 1)}>
                                <Minus className="h-3.5 w-3.5" />
                              </button>
                              <span className="min-w-5 text-center text-xs font-bold">{quantity}</span>
                              <button className="grid h-7 w-7 place-items-center rounded-md hover:bg-ink-100" onClick={() => setQuantity(item.item_id, quantity + 1)}>
                                <Plus className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ) : (
                            <Button size="sm" variant="soft" disabled={!item.is_available} onClick={() => addItem(item)}>
                              <Plus className="h-3.5 w-3.5" /> {t("menu.add")}
                            </Button>
                          )}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>

              <div className="mt-6 flex items-center justify-between">
                <p className="text-sm text-ink-500">
                  {(menu.data.page - 1) * menu.data.page_size + 1}–{Math.min(menu.data.page * menu.data.page_size, menu.data.total)} /{" "}
                  {menu.data.total}
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="icon" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                    <ChevronLeft className="h-4 w-4 rtl:rotate-180" />
                  </Button>
                  <span className="min-w-20 text-center text-sm font-semibold text-ink-700">
                    {menu.data.page} / {menu.data.pages}
                  </span>
                  <Button variant="secondary" size="icon" disabled={page >= menu.data.pages} onClick={() => setPage((prev) => prev + 1)}>
                    <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>

        <div id="cart" className="hidden lg:sticky lg:top-24 lg:block">
          <CartPanel
            lines={lines}
            subtotal={subtotal}
            methods={methods.data ?? []}
            onQuantity={setQuantity}
            onRemove={remove}
            onClear={clear}
            onPlaced={(order) => {
              queryClient.invalidateQueries({ queryKey: ["my-orders"] });
              setMobileCart(false);
              navigate(`/orders/${order.order_id}`);
            }}
          />
        </div>
      </div>

      {count ? (
        <div className="fixed inset-x-4 bottom-4 z-30 lg:hidden">
          <button
            onClick={() => setMobileCart(true)}
            className="flex w-full items-center justify-between rounded-2xl bg-ink-900 px-5 py-4 text-white shadow-2xl"
          >
            <span className="inline-flex items-center gap-2 text-sm font-bold">
              <ShoppingBag className="h-4 w-4" /> {count} {t("common.items")}
            </span>
            <span className="font-display text-base font-extrabold">{money(subtotal)}</span>
          </button>
        </div>
      ) : null}

      <Modal
        open={mobileCart}
        onClose={() => setMobileCart(false)}
        title={t("menu.cart")}
        size="md"
      >
        <CartPanel
          lines={lines}
          subtotal={subtotal}
          methods={methods.data ?? []}
          onQuantity={setQuantity}
          onRemove={remove}
          onClear={clear}
          onPlaced={(order) => {
            queryClient.invalidateQueries({ queryKey: ["my-orders"] });
            setMobileCart(false);
            navigate(`/orders/${order.order_id}`);
          }}
          compact
        />
      </Modal>
    </div>
  );
}

function CartPanel({
  lines,
  subtotal,
  methods,
  onQuantity,
  onRemove,
  onClear,
  onPlaced,
  compact
}: {
  lines: ReturnType<typeof useCart>["lines"];
  subtotal: number;
  methods: PaymentMethod[];
  onQuantity: (itemId: number, quantity: number) => void;
  onRemove: (itemId: number) => void;
  onClear: () => void;
  onPlaced: (order: Order) => void;
  compact?: boolean;
}) {
  const { t, pick } = useI18n();
  const toast = useToast();
  const [paymentMethod, setPaymentMethod] = useState("pay_at_counter");
  const [notes, setNotes] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      const idempotencyKey =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `order-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      return api<{ order: Order; message: string }>("/orders", {
        method: "POST",
        body: {
          items: lines.map((line) => ({ item_id: line.item_id, quantity: line.quantity })),
          payment_method: paymentMethod,
          order_notes: notes.trim() || undefined,
          idempotency_key: idempotencyKey
        }
      });
    },
    onSuccess: (data) => {
      toast.success(`${t("menu.orderPlaced")} · #${data.order.order_id}`);
      onClear();
      setNotes("");
      onPlaced(data.order);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  return (
    <Card className={clsx("overflow-hidden", compact ? "border-0 shadow-none" : "")}>
      <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
        <h2 className="inline-flex items-center gap-2 font-display text-base font-bold text-ink-900">
          <ShoppingCart className="h-4.5 w-4.5 text-brand-600" /> {t("menu.cart")}
        </h2>
        {lines.length ? (
          <button className="text-xs font-semibold text-ink-400 hover:text-rose-600" onClick={onClear}>
            {t("menu.clear")}
          </button>
        ) : null}
      </div>

      {!lines.length ? (
        <div className="px-5 py-10 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">
            <Sparkles className="h-6 w-6" />
          </div>
          <p className="text-sm font-semibold text-ink-800">{t("menu.emptyCart")}</p>
          <p className="mt-1 text-xs text-ink-400">{pick("Your total appears here.", "إجمالي طلبك سيظهر هنا.")}</p>
        </div>
      ) : (
        <div className="space-y-3 px-5 py-4">
          {lines.map((line) => (
            <div key={line.item_id} className="flex items-start gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ink-100 text-xs font-extrabold text-ink-500">
                {line.quantity}×
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink-900">{pick(line.item_name, line.item_name_ar)}</p>
                <p className="text-xs text-ink-400">{money(line.price)}</p>
                <div className="mt-1.5 flex items-center gap-1">
                  <button className="grid h-6 w-6 place-items-center rounded border border-ink-200 hover:bg-ink-50" onClick={() => onQuantity(line.item_id, line.quantity - 1)}>
                    <Minus className="h-3 w-3" />
                  </button>
                  <span className="min-w-6 text-center text-xs font-bold">{line.quantity}</span>
                  <button className="grid h-6 w-6 place-items-center rounded border border-ink-200 hover:bg-ink-50" onClick={() => onQuantity(line.item_id, line.quantity + 1)}>
                    <Plus className="h-3 w-3" />
                  </button>
                  <button className="ms-1 grid h-6 w-6 place-items-center rounded text-ink-400 hover:bg-rose-50 hover:text-rose-600" onClick={() => onRemove(line.item_id)}>
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
              <p className="shrink-0 text-sm font-bold text-ink-800">{money(line.price * line.quantity)}</p>
            </div>
          ))}

          <div className="mt-4 space-y-3 border-t border-ink-100 pt-4">
            <SelectField label={t("menu.paymentMethod")} value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>
              {methods.length ? (
                methods.map((method) => (
                  <option key={method.code} value={method.code}>
                    {pick(method.name, method.name_ar)}
                  </option>
                ))
              ) : (
                <option value="pay_at_counter">{pick("Pay at counter", "الدفع عند الكاشير")}</option>
              )}
            </SelectField>
            <TextAreaField label={t("menu.orderNotes")} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={500} placeholder={pick("No onions, extra sauce…", "بدون بصل، صوص إضافي…")} />
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3.5 py-3">
              <span className="text-sm font-semibold text-ink-600">{t("common.total")}</span>
              <span className="font-display text-lg font-extrabold text-ink-900">{money(subtotal)}</span>
            </div>
            <Button className="w-full" size="lg" loading={mutation.isPending} disabled={!lines.length} onClick={() => mutation.mutate()}>
              <ShoppingBag className="h-4 w-4" /> {t("menu.checkout")}
            </Button>
            <p className="text-center text-[10px] text-ink-400">{pick("Prices are read from the live menu database.", "الأسعار مقروءة من قاعدة بيانات المنيو.")}</p>
          </div>
        </div>
      )}
    </Card>
  );
}
