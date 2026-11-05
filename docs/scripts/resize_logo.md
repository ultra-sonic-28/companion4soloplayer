# Logo resize

This page describes how Companion4SoloPlayer resize its logo.

## Process Flow

```mermaid
flowchart TD
    Start([Start]) --> CheckExists{logo-64x64.png<br/>exists?}
    
    CheckExists -- No --> InfoNotExist[/Print: does not exist/]
    InfoNotExist --> CallGen1
    
    CheckExists -- Yes --> GetSrcMtime[Get SRC mtime]
    GetSrcMtime --> GetDstMtime[Get DST mtime]
    GetDstMtime --> CheckMtime{SRC mtime ><br/>DST mtime?}
    
    CheckMtime -- Yes --> InfoNewer[/Print: Source is newer/]
    InfoNewer --> CallGen2
    
    CheckMtime -- No --> InfoSkip[/Print: up to date/]
    InfoSkip --> EndSkip([End])
    
    subgraph generate_logo process
        CallGen1[Call generate_logo] --> OpenImg[Open SRC image]
        CallGen2[Call generate_logo] --> OpenImg
        OpenImg --> ResizeImg[Resize to 64x64]
        ResizeImg --> SaveImg[Save as PNG]
        SaveImg --> PrintOK[/Print: OK generated/]
    end
    
    PrintOK --> EndGen([End])

    %% Définition des styles
    classDef printStyle fill:#FFF3E0,stroke:#FF9800,stroke-width:2px,color:#333
    classDef startEnd fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    
    %% Application des styles
    class InfoNotExist,InfoNewer,InfoSkip,PrintOK printStyle
    class Start,EndSkip,EndGen startEnd
```

## Sequence diagram

```mermaid
sequenceDiagram
    participant User as Script Entry
    participant Main as main()
    participant Gen as generate_logo()
    participant FS as FileSystem
    participant PIL as PIL.Image

    User->>Main: main()
    Main->>FS: DST.exists()
    
    alt DST (logo-64x64.png) n'existe pas
        FS-->>Main: False
        Main->>Main: Print "[INFO] does not exist..."
        Main->>Gen: generate_logo()
        Gen->>PIL: Image.open(SRC)
        PIL-->>Gen: img
        Gen->>PIL: img.resize(size)
        PIL-->>Gen: img (resized)
        Gen->>PIL: img.save(DST, format='PNG')
        Gen-->>User: Print "[OK] generated."
        
    else DST (logo-64x64.png) existe
        FS-->>Main: True
        Main->>FS: SRC.stat().st_mtime
        FS-->>Main: src_mtime
        Main->>FS: DST.stat().st_mtime
        FS-->>Main: dst_mtime
        
        alt src_mtime > dst_mtime (Source plus récente)
            Main->>Main: Print "[INFO] Source is newer..."
            Main->>Gen: generate_logo()
            Gen->>PIL: Image.open(SRC)
            PIL-->>Gen: img
            Gen->>PIL: img.resize(size)
            PIL-->>Gen: img (resized)
            Gen->>PIL: img.save(DST, format='PNG')
            Gen-->>User: Print "[OK] generated."
            
        else src_mtime <= dst_mtime (Destination à jour)
            Main->>Main: Print "[SKIP] up to date."
        end
    end
```

::: resize_logo