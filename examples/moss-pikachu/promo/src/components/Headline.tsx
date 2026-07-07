import { DropText } from "./DropText";

/** Large display headline with editorial drop motion */
export const Headline: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
  delay?: number;
  align?: "left" | "center";
  variant?: "drop" | "slam" | "fade";
  dropDistance?: number;
}> = ({
  children,
  size = 72,
  color = "#F1F1F1",
  delay = 0,
  align = "center",
  variant = "drop",
  dropDistance = 120,
}) => (
  <DropText
    size={size}
    color={color}
    delay={delay}
    align={align}
    variant={variant}
    dropDistance={dropDistance}
    weight={700}
  >
    {children}
  </DropText>
);
