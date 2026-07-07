import { Img, staticFile } from "remotion";

export const MossWordmark: React.FC<{
  variant?: "light" | "dark";
  width?: number;
}> = ({ variant = "light", width = 280 }) => (
  <Img
    src={staticFile(
      variant === "dark"
        ? "branding/moss/wordmark-dark.png"
        : "branding/moss/wordmark-light.png",
    )}
    style={{ width, height: "auto" }}
  />
);

export const MossSymbol: React.FC<{ size?: number; opacity?: number }> = ({
  size = 40,
  opacity = 0.5,
}) => (
  <Img
    src={staticFile("branding/moss/symbol-light.png")}
    style={{ width: size, height: size, opacity }}
  />
);
