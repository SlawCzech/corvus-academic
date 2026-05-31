import { IconServer, IconRefresh, IconFileTypePdf } from "@tabler/icons-react"
import type { FC } from "react"

interface MetaItem {
  Icon: FC<{ size?: number; className?: string; "aria-hidden"?: boolean }>
  text: string
}

const ITEMS: MetaItem[] = [
  {
    Icon: IconServer,
    text: "Działa lokalnie — dane nie wychodzą z sieci",
  },
  {
    Icon: IconRefresh,
    text: "Qwen lokalnie lub Claude / GPT przez API",
  },
  {
    Icon: IconFileTypePdf,
    text: "PDF i DOCX do 50 MB",
  },
]

export default function MetaBar() {
  return (
    <div className="max-w-[580px] mx-auto px-8">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {ITEMS.map(({ Icon, text }) => (
          <div key={text} className="flex items-center gap-1.5">
            <Icon
              size={13}
              aria-hidden
              className="text-gray-400 dark:text-gray-500"
            />
            <span className="text-[12px] text-gray-400 dark:text-gray-500">
              {text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
