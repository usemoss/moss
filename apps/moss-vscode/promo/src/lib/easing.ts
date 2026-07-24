import { Easing } from "remotion";

export const smoothEase = Easing.bezier(0.16, 1, 0.3, 1);
export const cinematicEase = Easing.bezier(0.22, 1, 0.36, 1);
export const dropEase = Easing.bezier(0.34, 1.2, 0.64, 1);
export const snapEase = Easing.bezier(0.34, 1.56, 0.64, 1);
/** Heavy editorial slam — overshoots then settles */
export const slamEase = Easing.bezier(0.22, 1.35, 0.36, 1);
