import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  UtensilsCrossed
} from "lucide-react";
import { useDeferredValue, useState } from "react";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Loading,
  Modal,
  PageHeader,
  SelectField,
  TextAreaField,
  TextField,
  useToast
} from "../../components/ui";
import { api, errorMessage, qs } from "../../lib/api";
import { money } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import type { Category, MenuItem, Paginated } from "../../lib/types";

interface MenuResponse extends Paginated<MenuItem> {
  pages: number;
}

interface ItemForm {
  category_id: string;
  item_name: string;
  item_name_ar: string;
  price: string;
  description: string;
  description_ar: string;
  preparation_time: string;
  synonyms: string;
  image_url: string;
  is_available: boolean;
  is_featured: boolean;
}

const emptyForm: ItemForm = {
  category_id: "",
  item_name: "",
  item_name_ar: "",
  price: "",
  description: "",
  description_ar: "",
  preparation_time: "15",
  synonyms: "",
  image_url: "",
  is_available: true,
  is_featured: false
};

export default function MenuAdmin() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [category, setCategory] = useState<string>("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [form, setForm] = useState<ItemForm>(emptyForm);
  const [retiring, setRetiring] = useState<MenuItem | null>(null);

  const categories = useQuery({
    queryKey: ["categories", "all"],
    queryFn: () => api<Category[]>("/menu/categories?include_inactive=true")
  });

  const menu = useQuery({
    queryKey: ["menu", "admin", deferredSearch, category, page],
    queryFn: () =>
      api<MenuResponse>(
        `/menu${qs({
          q: deferredSearch || undefined,
          category_id: category || undefined,
          page,
          page_size: 20,
          sort: "name"
        })}`
      )
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm, category_id: categories.data?.[0]?.category_id ? String(categories.data[0].category_id) : "" });
    setOpen(true);
  };

  const openEdit = (item: MenuItem) => {
    setEditing(item);
    setForm({
      category_id: String(item.category_id),
      item_name: item.item_name,
      item_name_ar: item.item_name_ar,
      price: String(item.price),
      description: item.description ?? "",
      description_ar: item.description_ar ?? "",
      preparation_time: item.preparation_time != null ? String(item.preparation_time) : "15",
      synonyms: item.synonyms ?? "",
      image_url: item.image_url ?? "",
      is_available: item.is_available,
      is_featured: item.is_featured
    });
    setOpen(true);
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = {
        category_id: Number(form.category_id),
        item_name: form.item_name.trim(),
        item_name_ar: form.item_name_ar.trim(),
        price: Number(form.price),
        description: form.description.trim() || undefined,
        description_ar: form.description_ar.trim() || undefined,
        preparation_time: form.preparation_time ? Number(form.preparation_time) : 15,
        synonyms: form.synonyms.trim() || undefined,
        image_url: form.image_url.trim() || undefined,
        is_available: form.is_available,
        is_featured: form.is_featured
      };
      return editing
        ? api<MenuItem>(`/menu/${editing.item_id}`, { method: "PATCH", body })
        : api<MenuItem>("/menu", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(editing ? pick("Menu item updated", "تم تحديث الصنف") : pick("Menu item created", "تم إضافة الصنف"));
      queryClient.invalidateQueries({ queryKey: ["menu"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      setOpen(false);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const retireMutation = useMutation({
    mutationFn: () => api(`/menu/${retiring?.item_id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success(t("menuAdmin.retired"));
      queryClient.invalidateQueries({ queryKey: ["menu"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      setRetiring(null);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  const totalPages = menu.data?.pages ?? 1;

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("menuAdmin.title")}
        subtitle={t("menuAdmin.subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void menu.refetch()} loading={menu.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" /> {t("menuAdmin.addItem")}
            </Button>
          </div>
        }
      />

      <Card className="mb-4 flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            className="field ps-9"
            placeholder={pick("Search the menu…", "ابحث في المنيو…")}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>
        <SelectField
          value={category}
          onChange={(event) => {
            setCategory(event.target.value);
            setPage(1);
          }}
          className="sm:w-60"
        >
          <option value="">{pick("All categories", "كل الفئات")}</option>
          {(categories.data ?? []).map((row) => (
            <option key={row.category_id} value={row.category_id}>
              {pick(row.category_name, row.category_name_ar || row.category_name)} ({row.item_count})
            </option>
          ))}
        </SelectField>
      </Card>

      {menu.isLoading ? (
        <Loading />
      ) : !menu.data?.items.length ? (
        <EmptyState
          title={pick("No menu items match this filter.", "لا توجد أصناف مطابقة.")}
          icon={<UtensilsCrossed className="h-6 w-6" />}
        />
      ) : (
        <>
          <Card className="overflow-hidden">
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("common.name")}</th>
                    <th>{t("menuAdmin.category")}</th>
                    <th>{t("common.price")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("menuAdmin.prepTime")}</th>
                    <th className="text-end">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {menu.data.items.map((item) => (
                    <tr key={item.item_id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <span className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-xl bg-ink-100 text-ink-400">
                            {item.image_url ? (
                              <img src={item.image_url} alt="" className="h-full w-full object-cover" loading="lazy" />
                            ) : (
                              <UtensilsCrossed className="h-5 w-5" />
                            )}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-ink-900">
                              {pick(item.item_name, item.item_name_ar)}
                              {item.is_featured ? <Sparkles className="ms-1.5 inline h-3.5 w-3.5 text-brand-500" /> : null}
                            </p>
                            <p className="truncate text-xs text-ink-400">
                              {pick(item.item_name_ar, item.item_name)}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="text-xs text-ink-500">
                        {pick(item.category_name ?? "", item.category_name_ar || item.category_name || "")}
                      </td>
                      <td className="font-semibold text-ink-800">{money(item.price)}</td>
                      <td>
                        <Badge tone={item.is_available ? "success" : "neutral"}>
                          {item.is_available ? t("menuAdmin.available") : pick("Unavailable", "غير متوفر")}
                        </Badge>
                      </td>
                      <td className="text-xs text-ink-500">
                        {item.preparation_time != null ? `${item.preparation_time} ${t("common.min")}` : "—"}
                      </td>
                      <td>
                        <div className="flex justify-end gap-1.5">
                          <Button size="sm" variant="secondary" onClick={() => openEdit(item)}>
                            <Pencil className="h-3.5 w-3.5" /> {t("common.edit")}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setRetiring(item)}>
                            <Trash2 className="h-3.5 w-3.5" /> {t("menuAdmin.retire")}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="mt-4 flex items-center justify-between">
            <p className="text-xs text-ink-500">
              {pick("Page", "صفحة")} {menu.data.page} / {totalPages} · {menu.data.total} {t("common.items")}
            </p>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                <ChevronLeft className="h-4 w-4 rtl:rotate-180" /> {t("common.back")}
              </Button>
              <Button size="sm" variant="secondary" disabled={page >= totalPages} onClick={() => setPage((prev) => prev + 1)}>
                {pick("Next", "التالي")} <ChevronRight className="h-4 w-4 rtl:rotate-180" />
              </Button>
            </div>
          </div>
        </>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t("common.edit") : t("menuAdmin.addItem")}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>{t("common.save")}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label={t("common.name")}
            value={form.item_name}
            onChange={(event) => setForm((prev) => ({ ...prev, item_name: event.target.value }))}
            minLength={2}
            required
          />
          <TextField
            label={t("menuAdmin.nameAr")}
            value={form.item_name_ar}
            onChange={(event) => setForm((prev) => ({ ...prev, item_name_ar: event.target.value }))}
            dir="rtl"
            required
          />
          <SelectField
            label={t("menuAdmin.category")}
            value={form.category_id}
            onChange={(event) => setForm((prev) => ({ ...prev, category_id: event.target.value }))}
            required
          >
            <option value="" disabled>{pick("Select a category", "اختر فئة")}</option>
            {(categories.data ?? []).map((row) => (
              <option key={row.category_id} value={row.category_id}>
                {pick(row.category_name, row.category_name_ar || row.category_name)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={`${t("common.price")} (EGP)`}
            type="number"
            min={0.01}
            step="0.01"
            value={form.price}
            onChange={(event) => setForm((prev) => ({ ...prev, price: event.target.value }))}
            required
          />
          <TextField
            label={t("menuAdmin.prepTime")}
            type="number"
            min={0}
            max={240}
            value={form.preparation_time}
            onChange={(event) => setForm((prev) => ({ ...prev, preparation_time: event.target.value }))}
          />
          <TextField
            label={pick("Synonyms (comma separated)", "مرادفات (مفصولة بفاصلة)")}
            value={form.synonyms}
            onChange={(event) => setForm((prev) => ({ ...prev, synonyms: event.target.value }))}
            hint={pick("Used by the AI kiosk matcher", "يستخدمها مطابق كشك الذكاء الاصطناعي")}
          />
          <div className="sm:col-span-2">
            <TextField
              label={pick("Image URL", "رابط الصورة")}
              value={form.image_url}
              onChange={(event) => setForm((prev) => ({ ...prev, image_url: event.target.value }))}
              placeholder="/uploads/… or https://…"
            />
          </div>
          <TextAreaField
            label={`${t("menuAdmin.description")} (EN)`}
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
          />
          <TextAreaField
            label={`${t("menuAdmin.description")} (AR)`}
            value={form.description_ar}
            onChange={(event) => setForm((prev) => ({ ...prev, description_ar: event.target.value }))}
            dir="rtl"
          />
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-ink-300 text-brand-600"
              checked={form.is_available}
              onChange={(event) => setForm((prev) => ({ ...prev, is_available: event.target.checked }))}
            />
            {t("menuAdmin.available")}
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-ink-300 text-brand-600"
              checked={form.is_featured}
              onChange={(event) => setForm((prev) => ({ ...prev, is_featured: event.target.checked }))}
            />
            {t("menuAdmin.featured")}
          </label>
        </div>
        {form.image_url ? (
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-ink-100 bg-ink-50 p-3">
            <span className="grid h-16 w-16 place-items-center overflow-hidden rounded-lg bg-white ring-1 ring-ink-100">
              {form.image_url ? <img src={form.image_url} alt="" className="h-full w-full object-cover" /> : <ImageIcon className="h-5 w-5 text-ink-300" />}
            </span>
            <p className="text-xs text-ink-500">{pick("Image preview", "معاينة الصورة")}</p>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={Boolean(retiring)}
        title={t("menuAdmin.retire")}
        description={
          retiring
            ? pick(
                `“${retiring.item_name}” will be removed from ordering. Items with order history are retired, never deleted.`,
                `سيتم إيقاف «${retiring.item_name_ar}» من الطلب. الأصناف التي لها سجل طلبات يتم إيقافها وليس حذفها.`
              )
            : undefined
        }
        confirmLabel={t("menuAdmin.retire")}
        danger
        onClose={() => setRetiring(null)}
        onConfirm={() => retireMutation.mutate()}
      />
    </div>
  );
}
