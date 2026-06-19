import { SourceWorkDetailPage } from "@/components/source-work-detail-page";

type PageProps = {
  params: Promise<{ sourceWorkId: string }>;
};

export default async function Page({ params }: PageProps) {
  const { sourceWorkId } = await params;
  return <SourceWorkDetailPage sourceWorkId={sourceWorkId} />;
}
