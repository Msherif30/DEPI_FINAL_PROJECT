import { ArrowRight, Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function NotFound() {
  const { pick } = useI18n();
  return (
    <div className="grid min-h-screen place-items-center bg-ink-50 px-6">
      <div className="max-w-md text-center">
        <span className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-brand-100 text-brand-700">
          <Compass className="h-8 w-8" />
        </span>
        <p className="mt-5 font-display text-5xl font-extrabold text-ink-900">404</p>
        <h1 className="mt-2 font-display text-xl font-bold text-ink-800">
          {pick("This page is not on the menu.", "هذه الصفحة ليست على المنيو.")}
        </h1>
        <p className="mt-2 text-sm text-ink-500">
          {pick("The link may be old, or you may not have access to this area.", "قد يكون الرابط قديماً أو لا تملك صلاحية لهذه المنطقة.")}
        </p>
        <Link
          to="/"
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-800"
        >
          {pick("Back to RestoMate", "العودة إلى ريستوميت")}
          <ArrowRight className="h-4 w-4 rtl:rotate-180" />
        </Link>
      </div>
    </div>
  );
}
