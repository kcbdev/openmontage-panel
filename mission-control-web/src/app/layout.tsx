import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthLayout } from "./auth-layout";
import ToastLayout from "@/components/ToastLayout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mission Control",
  description: "OpenMontage Mission Control",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-50 text-gray-900`}>
        <ToastLayout>
          <AuthLayout>{children}</AuthLayout>
        </ToastLayout>
      </body>
    </html>
  );
}
