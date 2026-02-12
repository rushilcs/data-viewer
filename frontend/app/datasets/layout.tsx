"use client";

import AppShell from "@/components/AppShell";

export default function DatasetsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
