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

// TestVeoResourceLinkMatrix completes the cross-cutting sink matrix for veo at the
// resource_link seam (design #483 P4 Test Plan). The GCS multi-video and inline
// legs are covered by veo_resource_link_test.go; this adds the local-only and
// both-local+GCS legs and asserts the leading text (content[0]) is preserved
// byte-for-byte (back-compat) in every case.
func TestVeoResourceLinkMatrix(t *testing.T) {
	// Local-only sink: text has a local saved line, no gs:// URI resolved -> no link.
	t.Run("local-only sink -> no resource_link, text byte-identical", func(t *testing.T) {
		localText := "Video(s) saved locally to /tmp/out/clip.mp4"
		text := mcp.TextContent{Type: "text", Text: localText}
		content := appendVeoResourceLinks([]mcp.Content{text}, nil, "video/mp4")
		if len(content) != 1 {
			t.Fatalf("local-only produced %d content items, want 1 (no link)", len(content))
		}
		if got := content[0].(mcp.TextContent).Text; got != localText {
			t.Errorf("text drift on local-only path:\n got=%q\nwant=%q", got, localText)
		}
	})

	// Both local+GCS: text has BOTH the local and gs:// lines; one link per gs://
	// URI is appended and content[0] is preserved byte-for-byte.
	t.Run("both local+GCS -> resource_link present, text byte-identical", func(t *testing.T) {
		bothText := "Video(s) saved locally to /tmp/out/clip.mp4 and uploaded to gs://bucket/veo_outputs/clip.mp4"
		text := mcp.TextContent{Type: "text", Text: bothText}
		content := appendVeoResourceLinks([]mcp.Content{text},
			[]string{"gs://bucket/veo_outputs/clip.mp4"}, "video/mp4")
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
		if link.URI != "gs://bucket/veo_outputs/clip.mp4" {
			t.Errorf("resource_link URI = %q, want gs://bucket/veo_outputs/clip.mp4", link.URI)
		}
		if link.MIMEType != "video/mp4" {
			t.Errorf("resource_link MIMEType = %q, want video/mp4", link.MIMEType)
		}
	})
}
