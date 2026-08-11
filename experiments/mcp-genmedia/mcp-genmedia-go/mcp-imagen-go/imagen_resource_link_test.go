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
	"fmt"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestAppendImagenResourceLinksMultiImage asserts the GCS-sink result shape for a
// multi-image (num_images>1) imagen call: content[0] is the (unchanged) leading
// text item, followed by one resource_link per GCS artifact in generation order,
// each carrying its own 1:1-coupled MIME type (gcsSavedMimes[i]), the gs:// URI,
// and the 1-based "imagen output i of n" description (design #483, review NB-1).
// The upload/rename seams are not involved — the helper takes the already-resolved
// gs:// URIs, so the test is network-free.
func TestAppendImagenResourceLinksMultiImage(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Generated 3 images."}
	// Distinct MIME per artifact proves the gcsSavedMimes[i] 1:1 coupling: link i
	// must carry gcsSavedMimes[i], not a shared or drifted value.
	gcsSavedURIs := []string{
		"gs://bucket/pfx/sample_0.png",
		"gs://bucket/pfx/sample_1.jpg",
		"gs://bucket/pfx/sample_2.png",
	}
	gcsSavedMimes := []string{"image/png", "image/jpeg", "image/png"}

	content := appendImagenResourceLinks([]mcp.Content{text}, gcsSavedURIs, gcsSavedMimes)

	if len(content) != 4 {
		t.Fatalf("expected 4 content items (text + 3 links), got %d", len(content))
	}
	if got, ok := content[0].(mcp.TextContent); !ok || got.Text != text.Text {
		t.Fatalf("content[0] = %#v, want unchanged text %q", content[0], text.Text)
	}
	for i := 1; i <= 3; i++ {
		link, ok := content[i].(mcp.ResourceLink)
		if !ok {
			t.Fatalf("content[%d] = %T, want mcp.ResourceLink", i, content[i])
		}
		if link.Type != mcp.ContentTypeLink {
			t.Errorf("content[%d].Type = %q, want %q", i, link.Type, mcp.ContentTypeLink)
		}
		if link.URI != gcsSavedURIs[i-1] {
			t.Errorf("content[%d].URI = %q, want %q (order preserved)", i, link.URI, gcsSavedURIs[i-1])
		}
		if link.MIMEType != gcsSavedMimes[i-1] {
			t.Errorf("content[%d].MIMEType = %q, want %q (gcsSavedMimes[i] 1:1)", i, link.MIMEType, gcsSavedMimes[i-1])
		}
		if want := fmt.Sprintf("imagen output %d of 3", i); link.Description != want {
			t.Errorf("content[%d].Description = %q, want %q", i, link.Description, want)
		}
	}
}

// TestAppendImagenResourceLinksInlineNoLink is the inline/local-only regression
// guard: with no GCS artifacts the helper returns the content unchanged (no
// resource_link appended).
func TestAppendImagenResourceLinksInlineNoLink(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Inline image returned."}
	content := appendImagenResourceLinks([]mcp.Content{text}, nil, nil)
	if len(content) != 1 {
		t.Fatalf("expected 1 content item (text only), got %d", len(content))
	}
	if _, ok := content[0].(mcp.TextContent); !ok {
		t.Fatalf("content[0] = %T, want mcp.TextContent", content[0])
	}
}

// TestAppendImagenEditResourceLink asserts the imagen edit (single-artifact) GCS
// path appends exactly one resource_link after the text, with the edited gs:// URI,
// its MIME type, and the "imagen output 1 of 1" description (design #483).
func TestAppendImagenEditResourceLink(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Edited image saved."}
	content := appendImagenEditResourceLink([]mcp.Content{text}, "gs://bucket/edits/out.png", "image/png")

	if len(content) != 2 {
		t.Fatalf("expected 2 content items (text + 1 link), got %d", len(content))
	}
	if got, ok := content[0].(mcp.TextContent); !ok || got.Text != text.Text {
		t.Fatalf("content[0] = %#v, want unchanged text %q", content[0], text.Text)
	}
	link, ok := content[1].(mcp.ResourceLink)
	if !ok {
		t.Fatalf("content[1] = %T, want mcp.ResourceLink", content[1])
	}
	if link.Type != mcp.ContentTypeLink {
		t.Errorf("content[1].Type = %q, want %q", link.Type, mcp.ContentTypeLink)
	}
	if link.URI != "gs://bucket/edits/out.png" {
		t.Errorf("content[1].URI = %q, want gs://bucket/edits/out.png", link.URI)
	}
	if link.MIMEType != "image/png" {
		t.Errorf("content[1].MIMEType = %q, want image/png", link.MIMEType)
	}
	if link.Description != "imagen output 1 of 1" {
		t.Errorf("content[1].Description = %q, want %q", link.Description, "imagen output 1 of 1")
	}
}

// TestAppendImagenEditResourceLinkNoLink is the regression guard for the edit path:
// no edited GCS URI (inline/local-only) ⇒ content returned unchanged.
func TestAppendImagenEditResourceLinkNoLink(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Edited image returned inline."}
	content := appendImagenEditResourceLink([]mcp.Content{text}, "", "image/png")
	if len(content) != 1 {
		t.Fatalf("expected 1 content item (text only), got %d", len(content))
	}
	if _, ok := content[0].(mcp.TextContent); !ok {
		t.Fatalf("content[0] = %T, want mcp.TextContent", content[0])
	}
}
