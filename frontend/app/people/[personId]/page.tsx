import { PersonDetailPage } from "@/components/person-detail-page";

type PageProps = {
  params: Promise<{ personId: string }>;
};

export default async function Page({ params }: PageProps) {
  const { personId } = await params;
  return <PersonDetailPage personId={personId} />;
}
