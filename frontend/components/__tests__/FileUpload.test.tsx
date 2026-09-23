import { render, screen, act } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import type { DropzoneOptions, FileRejection } from "react-dropzone"

// vi.hoisted runs before vi.mock factories, making `captured` accessible inside the factory.
const captured = vi.hoisted<{ onDrop?: DropzoneOptions["onDrop"] }>(() => ({}))

vi.mock("react-dropzone", () => ({
  useDropzone: vi.fn((opts: DropzoneOptions) => {
    captured.onDrop = opts.onDrop
    return {
      getRootProps: () => ({}),
      getInputProps: () => ({ type: "file" as const }),
      isDragActive: false,
      open: vi.fn(),
    }
  }),
}))

import FileUpload from "../FileUpload"

function makeRejection(file: File, code: string): FileRejection {
  return { file, errors: [{ code, message: code }] }
}

const fakeEvent = new Event("drop") as unknown as Parameters<
  NonNullable<DropzoneOptions["onDrop"]>
>[2]

describe("FileUpload", () => {
  const onFileSelect = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    captured.onDrop = undefined
  })

  it("renders the drop zone with correct instructions", () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    expect(screen.getByTestId("dropzone")).toBeInTheDocument()
    expect(screen.getByText(/drag & drop your thesis/i)).toBeInTheDocument()
    expect(screen.getByText(/pdf or docx/i)).toBeInTheDocument()
  })

  it("accepts a PDF file and calls onFileSelect", async () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    const pdfFile = new File(["content"], "thesis.pdf", {
      type: "application/pdf",
    })
    await act(async () => {
      captured.onDrop?.([pdfFile], [], fakeEvent)
    })
    expect(onFileSelect).toHaveBeenCalledWith(pdfFile)
    expect(screen.getByTestId("selected-file")).toHaveTextContent("thesis.pdf")
  })

  it("accepts a DOCX file and calls onFileSelect", async () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    const docxFile = new File(["content"], "thesis.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    })
    await act(async () => {
      captured.onDrop?.([docxFile], [], fakeEvent)
    })
    expect(onFileSelect).toHaveBeenCalledWith(docxFile)
  })

  it("rejects an unsupported file type and shows an error", async () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    const txtFile = new File(["content"], "notes.txt", { type: "text/plain" })
    await act(async () => {
      captured.onDrop?.(
        [],
        [makeRejection(txtFile, "file-invalid-type")],
        fakeEvent,
      )
    })
    expect(onFileSelect).not.toHaveBeenCalled()
    expect(screen.getByTestId("rejection-error")).toHaveTextContent(
      /only pdf and docx/i,
    )
  })

  it("rejects a file over 25 MB and shows an error", async () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    const bigFile = new File(["x"], "big.pdf", { type: "application/pdf" })
    await act(async () => {
      captured.onDrop?.(
        [],
        [makeRejection(bigFile, "file-too-large")],
        fakeEvent,
      )
    })
    expect(onFileSelect).not.toHaveBeenCalled()
    expect(screen.getByTestId("rejection-error")).toHaveTextContent(
      /25 mb limit/i,
    )
  })

  it("shows the selected filename and formatted size", async () => {
    render(<FileUpload onFileSelect={onFileSelect} />)
    const file = new File(["a".repeat(2048)], "thesis.pdf", {
      type: "application/pdf",
    })
    await act(async () => {
      captured.onDrop?.([file], [], fakeEvent)
    })
    const info = screen.getByTestId("selected-file")
    expect(info).toHaveTextContent("thesis.pdf")
    expect(info).toHaveTextContent("2.0 KB")
  })
})
