import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { QueryClientProvider } from '@/components/QueryClientProvider';
import { AuthProvider } from '@/components/AuthProvider';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  weight: ['300', '400', '500', '600', '700', '800'],
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  weight: ['400', '500', '600', '700'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'SLM Studio — Train Your Own AI',
    template: '%s | SLM Studio',
  },
  description: 'Train Your Own AI. No Code. No Engineers. Your Data. Your Model. Your AI Assistant — Built in Minutes.',
  metadataBase: new URL('http://localhost:3000'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'SLM Studio',
    title: 'SLM Studio — Train Your Own AI',
    description: 'Train Your Own AI. No Code. No Engineers. Your Data. Your Model. Your AI Assistant — Built in Minutes.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SLM Studio — Train Your Own AI',
    description: 'Train Your Own AI. No Code. No Engineers. Your Data. Your Model. Your AI Assistant — Built in Minutes.',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} dark`}>
      <body className="font-sans bg-void text-ivory antialiased">
        {/* Skip link for accessibility */}
        <a
          href="#main-content"
          className="absolute top-[-40px] left-0 bg-gold text-void px-4 py-2 z-[10000] focus-visible:top-0 transition-all"
        >
          Skip to main content
        </a>

        {/* ARIA live regions */}
        <div aria-live="polite" aria-atomic="true" className="sr-only" id="aria-live-polite" />
        <div aria-live="assertive" aria-atomic="true" className="sr-only" id="aria-live-assertive" />

        <QueryClientProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </QueryClientProvider>
      </body>
    </html>
  );
}
