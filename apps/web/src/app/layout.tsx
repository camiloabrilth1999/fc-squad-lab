import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

const geistSans = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FC Squad Lab",
  description: "Resolutor personal de SBC de EA FC 27",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* suppressHydrationWarning: algunas extensiones de Chrome añaden atributos al <body> */}
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <Nav />
        {children}
      </body>
    </html>
  );
}
