import { notFound } from "next/navigation";
import DevelopmentCpfForm from "./DevelopmentCpfForm";

export const dynamic = "force-dynamic";

export default function DevelopmentCpfPage() {
  if (process.env.ENABLE_DEVELOPMENT_CPF_MOCK !== "true") notFound();
  return <DevelopmentCpfForm />;
}
