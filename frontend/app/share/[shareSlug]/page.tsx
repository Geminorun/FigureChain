import { SharePage } from "@/components/share-page";

type PageProps = {
  params: Promise<{ shareSlug: string }>;
};

export default async function Page({ params }: PageProps) {
  const { shareSlug } = await params;
  return <SharePage shareSlug={shareSlug} />;
}
