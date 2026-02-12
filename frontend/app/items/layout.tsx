"use client";

import AppShell from "@/components/AppShell";

export default function ItemsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
