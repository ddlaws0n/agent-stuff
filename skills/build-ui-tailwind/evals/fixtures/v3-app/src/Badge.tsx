type Status = "green" | "amber" | "red";

export function Badge({ status, label }: { status: Status; label: string }) {
  return (
    <span className={`relative start-0 rounded px-2 bg-${status}-500 text-white`}>
      {label}
    </span>
  );
}
