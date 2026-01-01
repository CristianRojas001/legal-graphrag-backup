import type { Metadata } from "next";
import "./globals.css";

// Using system fonts (Helvetica) to match Artisting design
// No need to import custom fonts

export const metadata: Metadata = {
  title: "Legal GraphRAG - Artisting",
  description: "Asistente legal basado en IA para artistas. Consulta normativa fiscal, derechos de autor y más, basado en fuentes oficiales del BOE y EUR-Lex.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
