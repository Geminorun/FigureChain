import { SourceRefDetailPage } from "@/components/source-ref-detail-page";

type PageProps = {
  params: Promise<{ sourceRefId: string }>;
};

export default async function Page({ params }: PageProps) {
  const { sourceRefId } = await params;
  return <SourceRefDetailPage sourceRefId={sourceRefId} />;
}
