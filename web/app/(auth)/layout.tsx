import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-6 py-4 border-b">
        <Link href="/" className="text-xl font-bold tracking-tight">
          Axis
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-6 py-10">
        {children}
      </main>
    </div>
  );
}
