"use client"

import { useCallback, useState } from "react"
import { useDropzone, type FileRejection } from "react-dropzone"

const MAX_SIZE_BYTES = 50 * 1024 * 1024

const ACCEPTED_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
    ".docx",
  ],
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface FileUploadProps {
  onFileSelect: (file: File) => void
  disabled?: boolean
}

export default function FileUpload({ onFileSelect, disabled }: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [rejectionError, setRejectionError] = useState<string | null>(null)

  const onDrop = useCallback(
    (accepted: File[], rejections: FileRejection[]) => {
      setRejectionError(null)
      if (rejections.length > 0) {
        const [first] = rejections
        const code = first.errors[0]?.code ?? "unknown"
        if (code === "file-too-large") {
          setRejectionError("File exceeds the 50 MB limit.")
        } else if (code === "file-invalid-type") {
          setRejectionError("Only PDF and DOCX files are accepted.")
        } else {
          setRejectionError(first.errors[0]?.message ?? "File rejected.")
        }
        return
      }
      if (accepted.length > 0) {
        const [file] = accepted
        setSelectedFile(file)
        onFileSelect(file)
      }
    },
    [onFileSelect],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_BYTES,
    multiple: false,
    disabled,
  })

  return (
    <div>
      <div
        {...getRootProps()}
        data-testid="dropzone"
        className={[
          "flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors",
          isDragActive
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-blue-400",
          disabled ? "pointer-events-none opacity-50" : "",
        ].join(" ")}
      >
        <input {...getInputProps()} data-testid="file-input" />
        <p className="text-lg font-medium text-gray-700">
          {isDragActive ? "Drop the file here…" : "Drag & drop your thesis"}
        </p>
        <p className="mt-1 text-sm text-gray-500">PDF or DOCX, max 50 MB</p>
      </div>

      {selectedFile && (
        <p data-testid="selected-file" className="mt-3 text-sm text-gray-700">
          {selectedFile.name} &mdash; {formatBytes(selectedFile.size)}
        </p>
      )}

      {rejectionError && (
        <p data-testid="rejection-error" className="mt-3 text-sm text-red-600">
          {rejectionError}
        </p>
      )}
    </div>
  )
}
