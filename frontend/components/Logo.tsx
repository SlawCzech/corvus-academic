import {
  BOOK_PATH,
  LEGS_PATH,
  LEGS_STROKE_WIDTH,
  MARK_VIEW_BOX,
  RAVEN_PATH,
  WORDMARK_PATH,
  WORDMARK_VIEW_BOX,
} from "@/lib/brand"

const SIZES = {
  sm: { mark: "h-9 w-9", wordmark: "h-[17px]" },
  md: { mark: "h-11 w-11", wordmark: "h-[19px]" },
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
        className={`${mark} shrink-0`}
      >
        <path d={RAVEN_PATH} />
        <path
          d={LEGS_PATH}
          fill="none"
          stroke="currentColor"
          strokeWidth={LEGS_STROKE_WIDTH}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <path d={BOOK_PATH} fillRule="evenodd" />
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
