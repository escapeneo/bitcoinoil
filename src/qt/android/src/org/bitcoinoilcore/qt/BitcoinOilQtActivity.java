package org.bitcoinoilcore.qt;

import android.os.Bundle;
import android.system.ErrnoException;
import android.system.Os;

import org.qtproject.qt5.android.bindings.QtActivity;

import java.io.File;

public class BitcoinOilQtActivity extends QtActivity
{
    @Override
    public void onCreate(Bundle savedInstanceState)
    {
        final File bitcoinoilDir = new File(getFilesDir().getAbsolutePath() + "/.bitcoinoil");
        if (!bitcoinoilDir.exists()) {
            bitcoinoilDir.mkdir();
        }

        super.onCreate(savedInstanceState);
    }
}
