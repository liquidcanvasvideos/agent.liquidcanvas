'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import { Bold, Italic, Underline as UnderlineIcon, Link as LinkIcon, Image as ImageIcon, Paperclip } from 'lucide-react'

interface RichEmailEditorProps {
  value: string
  onChange: (html: string, plainText?: string) => void
  placeholder?: string
  className?: string
}

function htmlToPlainText(html: string): string {
  if (!html) return ''
  if (typeof window === 'undefined') return html
  const el = document.createElement('div')
  el.innerHTML = html
  return (el.textContent || el.innerText || '').trim()
}

const ResizableImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-width') || element.getAttribute('width'),
        renderHTML: (attributes) => {
          if (!attributes.width) return {}
          return {
            'data-width': attributes.width,
            style: `width: ${attributes.width}; height: auto;`,
          }
        },
      },
    }
  },
})

export default function RichEmailEditor({ value, onChange, placeholder, className }: RichEmailEditorProps) {
  const [linkUrl, setLinkUrl] = useState('')
  const [showLinkEditor, setShowLinkEditor] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const extensions = useMemo(
    () => [
      StarterKit,
      Underline,
      Link.configure({
        openOnClick: true,
        autolink: true,
        linkOnPaste: true,
        HTMLAttributes: {
          rel: 'noopener noreferrer nofollow',
          target: '_blank',
        },
      }),
      ResizableImage.configure({
        inline: false,
        allowBase64: true,
      }),
      Placeholder.configure({
        placeholder: placeholder || 'Write your message...',
      }),
    ],
    [placeholder],
  )

  const editor = useEditor({
    extensions,
    content: value || '',
    editorProps: {
      attributes: {
        class:
          'tiptap-editor min-h-[180px] w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none',
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML()
      onChange(html, editor.getText())
    },
  })

  useEffect(() => {
    if (!editor) return
    const current = editor.getHTML()
    const next = value || ''
    if (current !== next) {
      editor.commands.setContent(next)
    }
  }, [editor, value])

  const applyLink = () => {
    if (!editor) return
    const url = linkUrl.trim()
    if (!url) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      setShowLinkEditor(false)
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
    setLinkUrl('')
    setShowLinkEditor(false)
  }

  const insertImageFromFile = async (file: File) => {
    if (!editor) return
    if (!file) return

    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(file)
    })

    if (!dataUrl) return
    editor.chain().focus().setImage({ src: dataUrl }).run()
  }

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const setImageWidth = (width: string | null) => {
    if (!editor) return
    if (!editor.isActive('image')) return
    editor.chain().focus().updateAttributes('image', { width }).run()
  }

  return (
    <div className={className || ''}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => editor?.chain().focus().toggleBold().run()}
          disabled={!editor}
          className={`px-2 py-1 rounded border text-xs flex items-center gap-1 ${
            editor?.isActive('bold') ? 'bg-olive-600 text-white border-olive-600' : 'bg-white text-gray-700 border-gray-300'
          }`}
        >
          <Bold className="w-3 h-3" />
          Bold
        </button>

        <button
          type="button"
          onClick={() => editor?.chain().focus().toggleItalic().run()}
          disabled={!editor}
          className={`px-2 py-1 rounded border text-xs flex items-center gap-1 ${
            editor?.isActive('italic') ? 'bg-olive-600 text-white border-olive-600' : 'bg-white text-gray-700 border-gray-300'
          }`}
        >
          <Italic className="w-3 h-3" />
          Italic
        </button>

        <button
          type="button"
          onClick={() => editor?.chain().focus().toggleUnderline().run()}
          disabled={!editor}
          className={`px-2 py-1 rounded border text-xs flex items-center gap-1 ${
            editor?.isActive('underline') ? 'bg-olive-600 text-white border-olive-600' : 'bg-white text-gray-700 border-gray-300'
          }`}
        >
          <UnderlineIcon className="w-3 h-3" />
          Underline
        </button>

        <button
          type="button"
          onClick={() => {
            if (!editor) return
            setShowLinkEditor((v) => !v)
            if (!showLinkEditor) {
              const existing = editor.getAttributes('link')?.href
              if (typeof existing === 'string' && existing.trim()) {
                setLinkUrl(existing.trim())
              }
            }
          }}
          disabled={!editor}
          className={`px-2 py-1 rounded border text-xs flex items-center gap-1 ${
            editor?.isActive('link') ? 'bg-olive-600 text-white border-olive-600' : 'bg-white text-gray-700 border-gray-300'
          }`}
        >
          <LinkIcon className="w-3 h-3" />
          Link
        </button>

        {showLinkEditor && (
          <div className="flex items-center gap-2">
            <input
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="Paste link URL"
              className="px-2 py-1 text-xs border border-gray-300 rounded w-64"
            />
            <button
              type="button"
              onClick={applyLink}
              disabled={!editor}
              className="px-2 py-1 rounded border text-xs bg-white text-gray-700 border-gray-300 disabled:opacity-50"
            >
              Apply
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={openFilePicker}
          disabled={!editor}
          className="px-2 py-1 rounded border text-xs flex items-center gap-1 bg-white text-gray-700 border-gray-300 disabled:opacity-50"
          title="Attach image"
        >
          <Paperclip className="w-3 h-3" />
          Attach
        </button>

        <button
          type="button"
          onClick={openFilePicker}
          disabled={!editor}
          className="px-2 py-1 rounded border text-xs flex items-center gap-1 bg-white text-gray-700 border-gray-300 disabled:opacity-50"
          title="Insert image"
        >
          <ImageIcon className="w-3 h-3" />
          Image
        </button>

        {editor?.isActive('image') && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setImageWidth('160px')}
              className="px-2 py-1 rounded border text-xs bg-white text-gray-700 border-gray-300"
            >
              Small
            </button>
            <button
              type="button"
              onClick={() => setImageWidth('260px')}
              className="px-2 py-1 rounded border text-xs bg-white text-gray-700 border-gray-300"
            >
              Medium
            </button>
            <button
              type="button"
              onClick={() => setImageWidth('360px')}
              className="px-2 py-1 rounded border text-xs bg-white text-gray-700 border-gray-300"
            >
              Large
            </button>
            <button
              type="button"
              onClick={() => setImageWidth('100%')}
              className="px-2 py-1 rounded border text-xs bg-white text-gray-700 border-gray-300"
            >
              Full
            </button>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (!file) return
            try {
              await insertImageFromFile(file)
            } catch {
              // ignore
            }
          }}
        />
      </div>

      <EditorContent editor={editor} />

      <div className="mt-2 text-[11px] text-gray-500">
        {htmlToPlainText(value).length} chars
      </div>
    </div>
  )
}
