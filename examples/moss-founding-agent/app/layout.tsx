import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bella Cucina — Order Online",
  description:
    "Fresh Italian cuisine, delivered to your door. Talk to our voice agent to place an order, check the menu, or ask about allergens.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
