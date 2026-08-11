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
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
)

// TestProcessGeminiImageResponseResourceLinks asserts the GCS-sink path returns
// content[0] as the (unchanged) text summary followed by one resource_link per
// uploaded artifact, each with the gs:// URI, MIME type, and 1-based
// "gemini output i of n" description (design #483). The upload seam is stubbed.
func TestProcessGeminiImageResponseResourceLinks(t *testing.T) {
	orig := uploadToGCSFn
	t.Cleanup(func() { uploadToGCSFn = orig })
	uploadToGCSFn = func(_ context.Context, _, _, _ string, _ []byte) error { return nil }

	resp := imageResponse(
		textPart("Two images."),
		imagePart("image/png", []byte("a")),
		imagePart("image/png", []byte("b")),
	)
	res, err := processGeminiImageResponse(context.Background(), resp, map[string]any{}, "", "gs://test-bucket/pfx", "test-bucket", "pfx")
	if err != nil {
		t.Fatalf("error: %v", err)
	}
	content := res.Content
	if len(content) != 3 {
		t.Fatalf("expected 3 content items (text + 2 links), got %d", len(content))
	}
	if _, ok := content[0].(mcp.TextContent); !ok {
		t.Fatalf("content[0] = %T, want mcp.TextContent", content[0])
	}
	for i := 1; i <= 2; i++ {
		link, ok := content[i].(mcp.ResourceLink)
		if !ok {
			t.Fatalf("content[%d] = %T, want mcp.ResourceLink", i, content[i])
		}
		if link.Type != "resource_link" {
			t.Errorf("content[%d].Type = %q, want resource_link", i, link.Type)
		}
		if !strings.HasPrefix(link.URI, "gs://test-bucket/pfx/") {
			t.Errorf("content[%d].URI = %q, want gs://test-bucket/pfx/ prefix", i, link.URI)
		}
		if link.MIMEType != "image/png" {
			t.Errorf("content[%d].MIMEType = %q, want image/png", i, link.MIMEType)
		}
		if want := fmt.Sprintf("gemini output %d of 2", i); link.Description != want {
			t.Errorf("content[%d].Description = %q, want %q", i, link.Description, want)
		}
	}
}

// TestProcessGeminiImageResponseInlineNoLink confirms the inline sink (no GCS, no
// local) still returns image content and no resource_link (regression guard).
func TestProcessGeminiImageResponseInlineNoLink(t *testing.T) {
	resp := imageResponse(imagePart("image/png", []byte("a")))
	res, err := processGeminiImageResponse(context.Background(), resp, map[string]any{}, "", "", "", "")
	if err != nil {
		t.Fatalf("error: %v", err)
	}
	for i, c := range res.Content {
		if _, ok := c.(mcp.ResourceLink); ok {
			t.Errorf("content[%d] is a resource_link; want none on the inline path", i)
		}
	}
}
