import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, MapPin, Pencil, Phone, Plus, RefreshCw, Truck, UserRound } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, Loading, Modal, PageHeader, TextAreaField, TextField, useToast } from "../../components/ui";
import { api, errorMessage } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Supplier } from "../../lib/types";

const emptyForm = {
  supplier_name: "",
  contact_name: "",
  phone: "",
  email: "",
  address: "",
  notes: "",
  is_active: true
};

export default function Suppliers() {
  const { t, pick } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const suppliers = useQuery({ queryKey: ["suppliers"], queryFn: () => api<Supplier[]>("/suppliers") });

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (supplier: Supplier) => {
    setEditing(supplier);
    setForm({
      supplier_name: supplier.supplier_name,
      contact_name: supplier.contact_name ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      notes: supplier.notes ?? "",
      is_active: supplier.is_active
    });
    setOpen(true);
  };

  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        supplier_name: form.supplier_name,
        contact_name: form.contact_name || undefined,
        phone: form.phone || undefined,
        email: form.email || undefined,
        address: form.address || undefined,
        notes: form.notes || undefined,
        is_active: form.is_active
      };
      return editing
        ? api(`/suppliers/${editing.supplier_id}`, { method: "PATCH", body })
        : api("/suppliers", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(editing ? pick("Supplier updated", "تم تحديث المورد") : pick("Supplier created", "تم إنشاء المورد"));
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      setOpen(false);
    },
    onError: (err) => toast.error(errorMessage(err))
  });

  return (
    <div>
      <PageHeader
        eyebrow={pick("Manager", "الإدارة")}
        title={t("suppliers.title")}
        subtitle={t("suppliers.subtitle")}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void suppliers.refetch()} loading={suppliers.isFetching}>
              <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
            </Button>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" /> {t("suppliers.add")}
            </Button>
          </div>
        }
      />

      {suppliers.isLoading ? (
        <Loading />
      ) : !suppliers.data?.length ? (
        <EmptyState
          title={t("suppliers.empty")}
          icon={<Truck className="h-6 w-6" />}
          action={<Button onClick={openCreate}><Plus className="h-4 w-4" /> {t("suppliers.add")}</Button>}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {suppliers.data.map((supplier) => (
            <Card key={supplier.supplier_id} className="card-pad transition hover:shadow-lg">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand-700"><Truck className="h-5 w-5" /></span>
                  <div>
                    <p className="font-display text-base font-bold text-ink-900">{supplier.supplier_name}</p>
                    <p className="text-xs text-ink-400">{supplier.contact_name || pick("No contact person", "لا يوجد مسؤول تواصل")}</p>
                  </div>
                </div>
                <Badge tone={supplier.is_active ? "success" : "neutral"}>{supplier.is_active ? t("common.active") : t("common.inactive")}</Badge>
              </div>
              <div className="mt-4 space-y-2 text-sm text-ink-600">
                {supplier.phone ? <p className="inline-flex items-center gap-2"><Phone className="h-4 w-4 text-ink-400" /> {supplier.phone}</p> : null}
                {supplier.email ? <p className="inline-flex items-center gap-2"><Mail className="h-4 w-4 text-ink-400" /> {supplier.email}</p> : null}
                {supplier.address ? <p className="inline-flex items-start gap-2"><MapPin className="mt-0.5 h-4 w-4 text-ink-400" /> {supplier.address}</p> : null}
                {supplier.contact_name ? <p className="inline-flex items-center gap-2"><UserRound className="h-4 w-4 text-ink-400" /> {supplier.contact_name}</p> : null}
              </div>
              {supplier.notes ? <p className="mt-3 line-clamp-2 rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-500">{supplier.notes}</p> : null}
              <div className="mt-4 flex justify-end">
                <Button size="sm" variant="secondary" onClick={() => openEdit(supplier)}>
                  <Pencil className="h-3.5 w-3.5" /> {t("common.edit")}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t("common.edit") : t("suppliers.add")}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>{t("common.save")}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label={t("common.name")} value={form.supplier_name} onChange={(event) => setForm((prev) => ({ ...prev, supplier_name: event.target.value }))} required />
          <TextField label={t("suppliers.contact")} value={form.contact_name} onChange={(event) => setForm((prev) => ({ ...prev, contact_name: event.target.value }))} />
          <TextField label={t("common.phone")} value={form.phone} onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))} />
          <TextField label={t("common.email")} type="email" value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} />
          <div className="sm:col-span-2">
            <TextField label={t("common.address")} value={form.address} onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))} />
          </div>
          <div className="sm:col-span-2">
            <TextAreaField label={t("common.notes")} value={form.notes} onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
            <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} className="h-4 w-4 rounded border-ink-300 text-brand-600" />
            {t("common.active")}
          </label>
        </div>
      </Modal>
    </div>
  );
}
