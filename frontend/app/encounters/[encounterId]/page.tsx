import { EncounterDetailPage } from "@/components/encounter-detail-page";

type PageProps = {
  params: Promise<{ encounterId: string }>;
};

export default async function Page({ params }: PageProps) {
  const { encounterId } = await params;
  return <EncounterDetailPage encounterId={encounterId} />;
}
