import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Indian IPO Prospective Shadow-Validation Engine',
  description: 'Point-in-time prospective evaluation, frozen inference and release gate surveillance dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
