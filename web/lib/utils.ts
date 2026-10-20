import { clsx, type ClassValue } from "clsx";
import { twMerge } from "cn";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
