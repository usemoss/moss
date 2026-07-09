import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { smoothEase } from "../lib/easing";

type MenuBarPetProps = {
  attentive?: boolean;
  opacity?: number;
};

export const MenuBarPet: React.FC<MenuBarPetProps> = ({
  attentive = false,
  opacity = 1,
}) => {
  const frame = useCurrentFrame();
  const bounce = attentive
    ? interpolate(frame % 24, [0, 12, 24], [0, -3, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smoothEase,
      })
    : 0;

  return (
    <Img
      src={staticFile("pet/capvolt-sticker.png")}
      style={{
        width: 24,
        height: 24,
        imageRendering: "pixelated",
        opacity,
        translate: `0 ${bounce}px`,
      }}
    />
  );
};
