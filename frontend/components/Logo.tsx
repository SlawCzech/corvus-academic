import {
  MARK_PATH,
  MARK_VIEW_BOX,
  WORDMARK_PATH,
  WORDMARK_VIEW_BOX,
} from "@/lib/brand"

const SIZES = {
  sm: { mark: "h-8 w-8", wordmark: "h-[17px]" },
  md: { mark: "h-9 w-9", wordmark: "h-[19px]" },
}

interface LogoProps {
  size?: keyof typeof SIZES
}

// Both shapes fill with currentColor, so the parent sets the logo's colour.
export default function Logo({ size = "md" }: LogoProps) {
  const { mark, wordmark } = SIZES[size]

  return (
    <>
      <svg
        viewBox={MARK_VIEW_BOX}
        aria-hidden="true"
        fill="currentColor"
        fillRule="evenodd"
        className={`${mark} shrink-0`}
      >
        <path d={MARK_PATH} />
      </svg>
      <svg
        viewBox={WORDMARK_VIEW_BOX}
        role="img"
        aria-label="Corvus"
        fill="currentColor"
        className={`${wordmark} w-auto shrink-0`}
      >
        <path d={WORDMARK_PATH} />
      </svg>
    </>
  )
}
