type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm">
      <p className="font-medium text-stone-800">{title}</p>
      <p className="mt-1 text-stone-600">{description}</p>
    </div>
  );
}
