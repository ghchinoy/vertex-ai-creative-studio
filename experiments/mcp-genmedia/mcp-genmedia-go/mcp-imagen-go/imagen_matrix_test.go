// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestImagenResourceLinkMatrix completes the cross-cutting sink matrix for imagen
// at the resource_link seam (design #483 P4 Test Plan). The GCS multi-image and
// inline legs are covered by imagen_resource_link_test.go; this adds the
// local-only and both-local+GCS legs and asserts the leading text (content[0]) is
// preserved byte-for-byte — the back-compat guarantee — in every case. The helper
// only decides the resource_link tail from the resolved gs:// URIs, so these are
// pure, network-free assertions.
func TestImagenResourceLinkMatrix(t *testing.T) {
	// Local-only sink: the handler's text carries a local saved-files line and no
	// gs:// URI is resolved, so no resource_link is appended and the text is intact.
	t.Run("local-only sink -> no resource_link, text byte-identical", func(t *testing.T) {
		localText := "Generated and saved 1 image(s): /tmp/out/shot.png"
		text := mcp.TextContent{Type: "text", Text: localText}
		content := appendImagenResourceLinks([]mcp.Content{text}, nil, nil)
		if len(content) != 1 {
			t.Fatalf("local-only produced %d content items, want 1 (no link)", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != localText {
			t.Errorf("text drift on local-only path:\n got=%q\nwant=%q", got, localText)
		}
	})

	// Both local+GCS: the handler's text carries BOTH the local saved-files line
	// and the GCS uploaded line; one resource_link is appended for the gs:// URI and
	// content[0] is preserved byte-for-byte (local text intact).
	t.Run("both local+GCS -> resource_link present, text byte-identical", func(t *testing.T) {
		bothText := "Generated and saved 1 image(s): /tmp/out/shot.png\n\n" +
			"Generated and uploaded 1 image(s) to GCS: gs://bucket/pfx/shot.png"
		text := mcp.TextContent{Type: "text", Text: bothText}
		content := appendImagenResourceLinks([]mcp.Content{text},
			[]string{"gs://bucket/pfx/shot.png"}, []string{"image/png"})
		if len(content) != 2 {
			t.Fatalf("both sink produced %d content items, want 2 (text + link)", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != bothText {
			t.Errorf("text drift on both path (back-compat):\n got=%q\nwant=%q", got, bothText)
		}
		link, ok := content[1].(mcp.ResourceLink)
		if !ok {
			t.Fatalf("content[1] = %T, want mcp.ResourceLink", content[1])
		}
		if link.URI != "gs://bucket/pfx/shot.png" {
			t.Errorf("resource_link URI = %q, want gs://bucket/pfx/shot.png", link.URI)
		}
	})

	// imagen edit (single artifact): both local+GCS -> one link, text preserved.
	t.Run("edit both local+GCS -> resource_link present, text byte-identical", func(t *testing.T) {
		editText := "Edited image saved locally to /tmp/out/edit.png and uploaded to gs://bucket/edits/edit.png"
		text := mcp.TextContent{Type: "text", Text: editText}
		content := appendImagenEditResourceLink([]mcp.Content{text}, "gs://bucket/edits/edit.png", "image/png")
		if len(content) != 2 {
			t.Fatalf("edit both sink produced %d content items, want 2", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != editText {
			t.Errorf("edit text drift:\n got=%q\nwant=%q", got, editText)
		}
		if content[1].(mcp.ResourceLink).URI != "gs://bucket/edits/edit.png" {
			t.Errorf("edit resource_link URI = %q, want gs://bucket/edits/edit.png", content[1].(mcp.ResourceLink).URI)
		}
	})
}
