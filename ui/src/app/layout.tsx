import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider } from "@/lib/i18n";
import { getThemeBootstrapScript } from "@/lib/theme";
import { ThemeProvider } from "@/lib/theme-context";
import { cn } from "@/lib/utils";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Serif } from "next/font/google";
import "./globals.css";

const notoSerif = Noto_Serif({ subsets: ["latin"], variable: "--font-serif" });

const notoSerifHeading = Noto_Serif({
  subsets: ["latin"],
  variable: "--font-heading",
});

const sans = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
});
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Lens",
  description: "渠道、模型组与系统配置管理后台",
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 15 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      refetchOnMount: false,
      retry: 1,
    },
  },
});

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-CN"
      suppressHydrationWarning
      className={cn(
        sans.variable,
        geistMono.variable,
        notoSerifHeading.variable,
        notoSerif.variable,
      )}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{ __html: getThemeBootstrapScript() }}
        />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <I18nProvider>
            <ThemeProvider>
              <TooltipProvider>
                {children}
                <SonnerToaster />
              </TooltipProvider>
            </ThemeProvider>
          </I18nProvider>
        </QueryClientProvider>
      </body>
    </html>
  );
}
