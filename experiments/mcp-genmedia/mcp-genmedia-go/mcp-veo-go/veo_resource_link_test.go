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

// TestAppendVeoResourceLinksMultiVideo asserts the GCS-sink result shape for a
// multi-video veo call: content[0] is the (unchanged) leading text item, followed
// by one resource_link per GCS video in generation order, each with the gs:// URI,
// the resolved video MIME type, and the 1-based "veo output i of n" description
// (design #483, review NB-1). The helper takes the already-resolved gs:// URIs, so
// the test is network-free.
func TestAppendVeoResourceLinksMultiVideo(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Generated 2 videos."}
	gcsVideoURIs := []string{
		"gs://bucket/veo_outputs/vid_0.mp4",
		"gs://bucket/veo_outputs/vid_1.mp4",
	}

	content := appendVeoResourceLinks([]mcp.Content{text}, gcsVideoURIs, "video/mp4")

	if len(content) != 3 {
		t.Fatalf("expected 3 content items (text + 2 links), got %d", len(content))
	}
	if got, ok := content[0].(mcp.TextContent); !ok || got.Text != text.Text {
		t.Fatalf("content[0] = %#v, want unchanged text %q", content[0], text.Text)
	}
	for i := 1; i <= 2; i++ {
		link, ok := content[i].(mcp.ResourceLink)
		if !ok {
			t.Fatalf("content[%d] = %T, want mcp.ResourceLink", i, content[i])
		}
		if link.Type != mcp.ContentTypeLink {
			t.Errorf("content[%d].Type = %q, want %q", i, link.Type, mcp.ContentTypeLink)
		}
		if link.URI != gcsVideoURIs[i-1] {
			t.Errorf("content[%d].URI = %q, want %q (order preserved)", i, link.URI, gcsVideoURIs[i-1])
		}
		if link.MIMEType != "video/mp4" {
			t.Errorf("content[%d].MIMEType = %q, want video/mp4", i, link.MIMEType)
		}
		if want := fmt.Sprintf("veo output %d of 2", i); link.Description != want {
			t.Errorf("content[%d].Description = %q, want %q", i, link.Description, want)
		}
	}
}

// TestAppendVeoResourceLinksInlineNoLink is the inline/local-only regression guard:
// with no GCS videos the helper returns the content unchanged.
func TestAppendVeoResourceLinksInlineNoLink(t *testing.T) {
	text := mcp.TextContent{Type: "text", Text: "Video saved locally only."}
	content := appendVeoResourceLinks([]mcp.Content{text}, nil, "video/mp4")
	if len(content) != 1 {
		t.Fatalf("expected 1 content item (text only), got %d", len(content))
	}
	if _, ok := content[0].(mcp.TextContent); !ok {
		t.Fatalf("content[0] = %T, want mcp.TextContent", content[0])
	}
}

// TestResolveVeoMIMEType covers the video/mp4 fallback flagged in review NB-1: an
// empty API MIME type defaults to video/mp4, while a non-empty value passes through
// unchanged (so a link never carries an empty MIME).
func TestResolveVeoMIMEType(t *testing.T) {
	cases := map[string]string{
		"":                "video/mp4",
		"video/mp4":       "video/mp4",
		"video/webm":      "video/webm",
		"video/quicktime": "video/quicktime",
	}
	for in, want := range cases {
		if got := resolveVeoMIMEType(in); got != want {
			t.Errorf("resolveVeoMIMEType(%q) = %q, want %q", in, got, want)
		}
	}
}
